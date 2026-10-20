# mlb-today v2: self-hosted refactor — project spec

Linear initiative: mlb-today (I-11). Glossary: `CONTEXT.md` at repo root. Decisions with rationale: `docs/adr/`.
This spec is the shared reference for every ticket in the project; a ticket needs its own `/planit` spec only where this document is silent.

## 1. Purpose

Replace the Azure Functions implementation of mlb-today with a single containerized Python service that runs on a self-hosted Ubuntu Mac Mini and sends one MLB **digest** email per day, 30 minutes before the day's first pitch. Keep every section the current email has, add yesterday's **results** and **standings**, and remove every dependency on Azure.

## 2. What the current app does (baseline to preserve)

Five Azure Functions sharing Azure Blob Storage:

| Function | Trigger | Does |
|---|---|---|
| `earliest_game_time` | timer `SCHEDULE_CRON` (09:00 UTC) | Fetches today's schedule, computes first pitch − 30 min, rewrites the app's own `PROBABLES_CRON` setting via the Azure management SDK |
| `get_batting_stats` | timer (10:15 UTC) | Fangraphs batting leaders → `batting.json` blob |
| `get_pitching_stats` | timer (10:00 UTC) | Fangraphs pitching leaders → `pitching.json` blob |
| `get_probables` | timer `PROBABLES_CRON` | Schedule + probables joined to stored Fangraphs data → `email_data.json` blob |
| `create_and_send_email` | blob trigger | Jinja2 render of `email.jinja2`, SMTP send via Fastmail |

Email sections today: matchups grouped by first pitch (team abbr + record, probable with W-L / ERA / xFIP / WAR, venue, TV broadcasts split national/home/away), batting leaderboard (Player, Team, AVG, HR, OPS, WAR), pitching leaderboard (Player, Team, Record, ERA, xFIP, WAR). Top 25 each, sorted by WAR. Subject: `MLB Today for {Month DD, YYYY}`.

Known bug to fix in the port: the template's "Misc" broadcast line prints `game.watch.away` instead of `game.watch.misc`.

## 3. Decisions (summary; see ADRs for rationale)

| Area | Decision |
|---|---|
| Runtime | One long-running container with an internal scheduler (ADR-0001). No HTTP server. |
| Pipeline | Fetch every source at send time in one pass; persist each successful raw response as a **source snapshot**; fall back to the snapshot on failure (ADR-0002). |
| Email transport | `Transport` protocol with two implementations: Resend (primary), SMTP/Fastmail (fallback). |
| Email authoring | MJML compiled by `mjml-python` (Rust `mrml`), rendered through Jinja2 (ADR-0003). Visual redesign, not a port of the old table template. |
| Results section | Final score (with innings if ≠ 9), R/H/E, W/L/S **decisions** with records, home-run hitters with season totals, non-final status for postponed/suspended games. |
| Standings | Six division tables: W, L, PCT, GB, L10, streak. Regular season only. |
| No-game days | Send nothing, except a **scores-only digest** at a fixed morning time when the previous day was a game day. |
| Toolchain | uv, ruff (lint + format), pyright, pytest, respx, httpx, pydantic v2 + pydantic-settings, Python 3.13. |
| Build/deploy | GitHub Actions: lint + test on every PR; build and push `ghcr.io/tomboone/mlb-today` on push to `release/v2` (`:edge`) and `main` (`:latest`). Watchtower on the Mini pulls new tags. |
| Alerting | Structured JSON logs to stdout; healthchecks.io ping on success, `/fail` on a failed send. No Sentry. |
| Branch flow | `release/v2` off `main`. Each ticket branches from and PRs into `release/v2`. One final PR merges `release/v2` → `main`. The Azure workflow keeps deploying `main` until then. |

## 4. Architecture

### 4.1 Package layout (`src` layout, package `mlb_today`)

```
src/mlb_today/
  __init__.py
  __main__.py            # `python -m mlb_today` → cli
  cli.py                 # typer/argparse: run | send | preview | health
  settings.py            # pydantic-settings; all env in one place
  logging.py             # structlog or stdlib JSON formatter config
  scheduler.py           # daily loop: compute send time, sleep, dispatch
  state.py               # last-sent marker on the data volume
  clock.py               # Clock protocol (now(), sleep_until()) for testability
  sources/
    http.py              # make_client: shared httpx.Client factory (timeout, retries, User-Agent)
    snapshot.py          # SnapshotStore: last good raw response per source on the data volume
    fetched.py           # Fetched[T] + fetch_or_snapshot: fetch, or fall back to the snapshot
    mlb.py               # MLB Stats API client: schedule, results, boxscore HRs, standings
    fangraphs.py         # Fangraphs leaders client
    models/              # pydantic models of raw payloads (one module per endpoint)
  digest/
    models.py            # Digest, Matchup, Probable, PitcherLine, Result, Decision, Standings, Leaderboard
    build.py             # raw payloads → Digest (pure functions, no I/O)
  render/
    templates/digest.mjml.j2
    render.py            # Digest → (subject, html, text)
  transport/
    base.py              # Transport protocol
    resend.py
    smtp.py
    chain.py             # try transports in order
  heartbeat.py           # healthchecks.io client
```

Rules: `sources/` and `transport/` are the only modules that do network I/O. `digest/build.py` and `render/` are pure and fully unit-tested from fixtures. `scheduler.py` orchestrates and is tested with a fake `Clock`.

### 4.2 Daily flow

1. **Boot** and **every day at `PLAN_TIME` (default 03:00 America/New_York)**: fetch today's schedule (Eastern date).
   - Games today → send time = earliest `gameDate` − `SEND_LEAD_MINUTES` (default 30). If that instant is already past (boot after send time, or very early game), send immediately unless the last-sent marker says today's digest already went out.
   - No games today, but games yesterday → send time = `SCORES_ONLY_TIME` (default 09:00 America/New_York).
   - Neither → log and sleep until next `PLAN_TIME`.
2. **At send time**: `send(date)`:
   1. Fetch all sources (§5). Each success writes a snapshot; each failure logs a warning and loads the snapshot for that source, tagging the digest with `stale: {source: snapshot_timestamp}`. If a source has no snapshot either, its section is omitted and the digest says so.
   2. Build `Digest` (pure).
   3. Render MJML → HTML + plain-text alternative.
   4. Send through the transport chain. First success wins.
   5. Write the last-sent marker `{date, sent_at, transport, message_id}`; ping heartbeat. On total transport failure: ping `/fail`, log at error, do **not** write the marker (a restart will retry).
3. Sleep until the next `PLAN_TIME`.

Date semantics: "today" and "yesterday" are Eastern-time calendar dates everywhere.

### 4.3 Restart safety

The last-sent marker on the data volume is the only thing that prevents a double send. On boot the scheduler reads it before deciding whether an already-past send time should fire. The container restarts on failure (`restart: unless-stopped`).

### 4.4 Health

`mlb-today health` exits 0 if the state file was touched within the last 26 hours (the scheduler touches it at each plan and each send). Docker `HEALTHCHECK` runs that command. No HTTP.

## 5. Sources

All HTTP through a shared `httpx.Client` with a 20 s timeout, 3 retries with backoff on 5xx/connect errors, and a descriptive `User-Agent`.

### 5.1 MLB Stats API (`https://statsapi.mlb.com`)

| Need | Request |
|---|---|
| Today's matchups | `GET /api/v1/schedule?sportId=1&startDate={d}&endDate={d}&timeZone=America/New_York&sortBy=gameDate,gameType&hydrate=team,broadcasts(all),venue(location),probablePitcher` |
| Yesterday's results | same endpoint for `{d-1}` with `hydrate=team,linescore,decisions` |
| Home runs per result | `GET /api/v1/game/{gamePk}/boxscore`; HR hitters are players in `teams.{home,away}.players` whose `stats.batting.homeRuns > 0`; season total is `seasonStats.batting.homeRuns`. Only called for games with status `Final`. |
| Standings | `GET /api/v1/standings?leagueId=103,104&season={yyyy}&standingsTypes=regularSeason&hydrate=team,division`; per `teamRecords[]`: `wins`, `losses`, `winningPercentage`, `gamesBack`, `streak.streakCode`, `records.splitRecords[type=lastTen]`. |

Matchup fields used: `gameDate`, `status.detailedState`, `teams.{away,home}.team.abbreviation`, `.leagueRecord.{wins,losses}`, `.probablePitcher.{id,fullName}`, `venue.name`, `venue.location.{city,stateAbbrev}`, `broadcasts[]` with `type == "TV"`, `isNational`, `homeAway`, `callSign`.

Result fields used: `status.detailedState` (Final / Postponed / Suspended / …), `linescore.{currentInning,innings[],teams.{away,home}.{runs,hits,errors}}`, `decisions.{winner,loser,save}.{id,fullName}`; decision records come from the pitching leaderboard by MLBAM id (W-L; saves count is `SV`).

Doubleheaders are two matchups/results with the same teams and distinct `gamePk`; render both.

### 5.2 Fangraphs (`https://www.fangraphs.com/api/leaders/major-league/data`)

Params: `pos=all&stats={bat|pit}&lg=all&qual=n&season={yyyy}&sortDir=default&sortStat=WAR&pageItems={n}`. Response `{"data": [...]}`.

- Pitching: request the full table (`pageItems` large, as today) because probables and decisions must be matched by `xMLBAMID` even when the pitcher is nowhere near the top 25. Fields: `PlayerName`, `TeamNameAbb`, `xMLBAMID`, `W`, `L`, `SV`, `ERA`, `xFIP`, `WAR`.
- Batting: top 25 is enough; request `pageItems=25`. Fields: `PlayerName`, `TeamNameAbb`, `AVG`, `HR`, `OBP`, `SLG`, `OPS`, `BABIP`, `WAR`.
- Season = the Eastern year of the digest date. Fangraphs is unofficial; the client must tolerate missing or string-typed numeric fields (coerce, default to `None`, never crash the digest).

## 6. Digest model (what the email shows)

```
Digest
  date: date                     # Eastern
  kind: "full" | "scores_only"
  stale: dict[str, datetime]     # source name → snapshot time, when fallback used
  unavailable: list[str]         # sources with no snapshot either; their sections are omitted
  matchups: list[Matchup]        # empty on scores_only
  results: list[Result]
  standings: list[DivisionStandings]   # 6, AL East … NL West
  batting: Leaderboard | None    # None when unavailable
  pitching: Leaderboard | None

Matchup: first_pitch, status, away: Side, home: Side, venue: str, tv: Broadcasts
Side: abbr, wins, losses, probable: Probable
Probable: name ("TBD" if none), line: PitcherLine | None
PitcherLine: w, l, era, xfip, war
Broadcasts: national[], home[], away[], misc[]

Result: status, innings (int | None when 9), away: ResultSide, home: ResultSide, decisions: Decisions | None, stale_note
ResultSide: abbr, runs, hits, errors, home_runs: list[HomeRun]
HomeRun: player, season_total
Decisions: winner: Decision, loser: Decision, save: Decision | None
Decision: name, wins, losses (or saves for save)

DivisionStandings: league, division, rows: list[StandingsRow]
StandingsRow: abbr, w, l, pct, gb ("-" for leader), last_ten, streak

Leaderboard: kind ("batting" | "pitching"), rows[25], as_of
```

Section order in the email: header (date, stale banner if any) → Today's matchups (grouped by first pitch, omitted on scores-only) → Yesterday's results → Standings → Batting leaders → Pitching leaders → footer.

Subject: `MLB Today — {Mon DD}` for full, `MLB Scores — {Mon DD}` for scores-only. Plain-text alternative generated from the same `Digest`.

## 7. Transport

```python
class Transport(Protocol):
    name: str
    def send(self, msg: Message) -> SendReceipt: ...   # raises TransportError
```

`Message`: `subject`, `html`, `text`, `to: list[str]`, `from_: str`. `ChainTransport([resend, smtp])` tries in order, logs each failure, returns the first receipt, raises `AllTransportsFailed` if none succeed.

- Resend: `resend` SDK, `RESEND_API_KEY`, `RESEND_FROM` (a verified sending domain on tomboone.com).
- SMTP: `smtplib.SMTP_SSL`, host/port/user/password/from from env (same names as today where possible).
- `DRY_RUN=true` replaces the chain with a transport that writes the HTML to the data volume and logs; used in staging and in `preview`.

## 8. Configuration (env, via pydantic-settings; `.env` on the Mini, never committed)

| Var | Default | Notes |
|---|---|---|
| `TZ_LOCAL` | `America/New_York` | date and time anchor |
| `PLAN_TIME` | `03:00` | daily schedule fetch |
| `SEND_LEAD_MINUTES` | `30` | |
| `SCORES_ONLY_TIME` | `09:00` | |
| `DATA_DIR` | `/data` | volume: snapshots, state, dry-run output |
| `RECIPIENTS` | required | comma-separated |
| `RESEND_API_KEY`, `RESEND_FROM` | | enables Resend transport |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SENDER_ADDRESS` | host `smtp.fastmail.com`, port `465` | enables SMTP transport |
| `TRANSPORTS` | `resend,smtp` | order of the chain |
| `HEALTHCHECKS_URL` | | ping URL; absent = heartbeat disabled |
| `DRY_RUN` | `false` | |
| `LOG_LEVEL` | `INFO` | |
| `MLB_API_BASE`, `FANGRAPHS_API_BASE` | prod URLs | overridable for tests |

## 9. CLI

- `mlb-today run` — the scheduler loop (container entrypoint).
- `mlb-today send [--date YYYY-MM-DD] [--dry-run]` — build and send one digest now.
- `mlb-today preview [--date] [--out digest.html] [--from-snapshots]` — render to a file without sending.
- `mlb-today health` — healthcheck exit code.

## 10. Testing conventions

- `tests/fixtures/{mlb,fangraphs}/*.json`: recorded real responses, trimmed to a few games / 30 players, captured once by a `scripts/record_fixtures.py` helper.
- `respx` mocks `httpx` at the client boundary; source client tests assert request params and parsed models.
- `digest/build.py` tests are pure: fixture payloads in, `Digest` out, including: TBD probable, pitcher absent from Fangraphs, postponed and suspended results, extra-inning result, doubleheader, no games today, no games yesterday, division leader `gb == "-"`.
- Rendering: snapshot tests of the compiled HTML (`syrupy`) for a full digest, a scores-only digest, and a stale digest; assert the HTML is under 150 KB.
- Scheduler: fake `Clock`; cases for boot-before-send, boot-after-send-with-marker, boot-after-send-without-marker, no games, scores-only day, early international game.
- Transport: `ChainTransport` fallback order; Resend and SMTP clients mocked.
- CI fails on ruff, pyright, or pytest failure. Coverage reported, not gated.

## 11. Container and deploy

- `Dockerfile`: multi-stage, `python:3.13-slim`, `uv sync --frozen --no-dev`, non-root user, `HEALTHCHECK CMD mlb-today health`, `CMD ["mlb-today", "run"]`.
- `deploy/docker-compose.yml`: `mlb-today` service with `env_file: .env`, volume `./data:/data`, `restart: unless-stopped`; `watchtower` service polling GHCR every 5 minutes with label-scoped updates.
- `deploy/README.md`: Mini setup (Docker install, clone `deploy/`, `.env`, `docker compose up -d`), how to check logs, how to run `preview`.
- Workflows: `ci.yml` (PRs and pushes: uv sync, ruff check, ruff format --check, pyright, pytest), `image.yml` (push to `release/v2` → `:edge` + sha; push to `main` → `:latest` + sha). The existing `azure-functions-app-python.yml` stays until the final cutover ticket deletes it.

## 12. Cutover (final milestone)

1. Run `:edge` on the Mini with `DRY_RUN=true` for several game days; compare output to the Azure email.
2. Switch `DRY_RUN=false` on the Mini and set `DISABLE_EMAIL_SENDING=True` on Azure for an overlap of at least three game days.
3. Final PR `release/v2` → `main`: deletes `function_app.py`, `host.json`, `.funcignore`, `local.settings.json`, `azurite-data/`, `azurite-debug.log`, `logs/`, `src/mlb_today/blueprints`, Azure services, the Azure workflow, and the Azure deps; updates README.
4. Delete the Azure Function App, storage account, and the GitHub OIDC secrets. Point Watchtower at `:latest`.

## 13. Out of scope

HTTP endpoints of any kind, box scores or play-by-play, per-user preferences or multiple recipients with different content, live or in-game updates, Sentry or any APM, a web archive of past digests.
