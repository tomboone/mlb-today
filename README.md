# MLB Today

A daily Major League Baseball digest email, sent 30 minutes before the day's first pitch.

mlb-today is a single long-running Python service, deployed as one container on a self-hosted Ubuntu box. It
plans each day at boot and again at `PLAN_TIME`, builds the digest from the MLB Stats API and Fangraphs at send time,
and delivers it through Resend, with SMTP as a fallback.

## What it sends

On a game day, one **digest** containing:

*   **Matchups**: each scheduled game with team records, probable pitchers and their season lines (W-L, ERA,
    xFIP, WAR), first pitch, venue and broadcasts.
*   **Results**: the previous game day's final scores, R/H/E, decisions and home runs.
*   **Standings**: the six division tables as of the previous game day.
*   **Leaderboards**: the season's top 25 batters and pitchers by WAR.

On a day with no games that follows a game day, a **scores-only digest** (results, standings and leaderboards) goes
out at `SCORES_ONLY_TIME` instead.

If a source is down at send time, the digest is built from that source's last successful response and says so.

See [`CONTEXT.md`](CONTEXT.md) for the glossary and [`docs/adr/`](docs/adr/) for the design decisions.

## Commands

| Command | Does |
|---|---|
| `mlb-today run` | Runs the scheduler loop (the container entrypoint) |
| `mlb-today send [--date YYYY-MM-DD] [--dry-run]` | Builds and sends one digest now |
| `mlb-today preview [--date YYYY-MM-DD] [--out digest.html] [--from-snapshots]` | Renders a digest to HTML and text files without sending |
| `mlb-today health` | Exits 0 if the scheduler has been active in the last 26 hours |

## Running locally

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```sh
uv sync
DATA_DIR=./data RECIPIENTS=you@example.com uv run mlb-today preview --out data/digest.html
```

That writes `data/digest.html` and `data/digest.txt`. `DATA_DIR` defaults to `/data`, which is the container's
volume, so set it when running outside Docker. The app reads only real environment variables, not a `.env` file.

Before opening a PR:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

## Deployment

[`deploy/README.md`](deploy/README.md) walks from a fresh Ubuntu install to a running digest: Docker, the GHCR
image, Resend, healthchecks.io, `.env`, and day-to-day operation. Pushes to `main` publish
`ghcr.io/tomboone/mlb-today:latest`, and Watchtower on the host picks up each new image.

## Configuration

All configuration comes from environment variables. [`deploy/.env.example`](deploy/.env.example) is the annotated
template.

| Variable | Default | Notes |
|---|---|---|
| `RECIPIENTS` | required | Comma-separated recipient addresses |
| `TZ_LOCAL` | `America/New_York` | Time zone for dates and the times below |
| `PLAN_TIME` | `03:00` | Daily schedule fetch |
| `SEND_LEAD_MINUTES` | `30` | Minutes before first pitch to send |
| `SCORES_ONLY_TIME` | `09:00` | Send time for a scores-only digest |
| `DATA_DIR` | `/data` | Snapshots, state and dry-run output |
| `RESEND_API_KEY`, `RESEND_FROM` | | Set both to enable the Resend transport |
| `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SENDER_ADDRESS` | | Set all three to enable the SMTP transport |
| `SMTP_HOST`, `SMTP_PORT` | `smtp.fastmail.com`, `465` | SMTP server (implicit TLS) |
| `TRANSPORTS` | `resend,smtp` | Order in which transports are tried |
| `HEALTHCHECKS_URL` | | healthchecks.io ping URL; unset disables the heartbeat |
| `DRY_RUN` | `false` | Write digests to `DATA_DIR/outbox` instead of sending them |
| `LOG_LEVEL` | `INFO` | |
| `MLB_API_BASE`, `FANGRAPHS_API_BASE` | production URLs | Overridable for tests |

## License

This project is licensed under the MIT License. See [`LICENSE.md`](LICENSE.md) for details.

## Disclaimer

This project retrieves data from MLB.com and Fangraphs.com. However, this project is not affiliated with, endorsed by,
or in any way officially connected with Major League Baseball or Fangraphs.
