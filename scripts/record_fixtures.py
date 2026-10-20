"""Record trimmed live MLB and Fangraphs responses into tests/fixtures/ (spec §5, §10).

    uv run scripts/record_fixtures.py --date 2026-09-15 [--keep-ids 592450,669203]

`--date` is the digest date: matchups come from that day, results from the day before.
Each schedule keeps its first 3 games, plus the first non-final, extra-inning, and doubleheader
game (with its other half) when the first 3 have none. Each Fangraphs table keeps its first
30 players plus any `--keep-ids` (MLBAM ids, e.g. probables or decision pitchers in the kept games).
Batting is requested with `pageItems=25` as the real client will (spec §5.2), so it holds
at most 25 players and `--keep-ids` only reaches pitchers outside the top 30.
"""

import argparse
import json
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from mlb_today.settings import Settings
from mlb_today.sources.http import make_client

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
GAMES = 3
PLAYERS = 30
FANGRAPHS_ALL = 2000

type Payload = dict[str, Any]


def _default(field: str) -> str:
    return Settings.model_fields[field].default


def _get(client: httpx.Client, url: str, params: dict[str, str | int] | None = None) -> Payload:
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _teams(game: Payload) -> tuple[int, int]:
    return game["teams"]["away"]["team"]["id"], game["teams"]["home"]["team"]["id"]


def _is_doubleheader(game: Payload) -> bool:
    return game.get("doubleHeader", "N") != "N"


EDGE_CASES: tuple[Callable[[Payload], bool], ...] = (
    lambda g: g["status"]["detailedState"] != "Final",
    lambda g: g.get("linescore", {}).get("currentInning", 0) > 9,
    _is_doubleheader,
)


def _trim(games: list[Payload]) -> list[Payload]:
    """The first GAMES games plus one of each edge case they lack (spec §10), in original order."""
    kept = set(range(min(GAMES, len(games))))
    for is_case in EDGE_CASES:
        if any(is_case(games[i]) for i in kept):
            continue
        first = next((i for i, g in enumerate(games) if is_case(g)), None)
        if first is not None:
            kept.add(first)
    # A doubleheader is only useful as a fixture with both halves.
    halves = {_teams(games[i]) for i in kept if _is_doubleheader(games[i])}
    kept |= {i for i, g in enumerate(games) if _is_doubleheader(g) and _teams(g) in halves}
    return [g for i, g in enumerate(games) if i in kept]


def _schedule(client: httpx.Client, day: date, hydrate: str) -> Payload:
    payload = _get(
        client,
        "/api/v1/schedule",
        {
            "sportId": 1,
            "startDate": day.isoformat(),
            "endDate": day.isoformat(),
            "timeZone": "America/New_York",
            "sortBy": "gameDate,gameType",
            "hydrate": hydrate,
        },
    )
    for day_entry in payload.get("dates", []):
        day_entry["games"] = _trim(day_entry["games"])
    return payload


def _boxscore(client: httpx.Client, game_pk: int) -> Payload:
    payload = _get(client, f"/api/v1/game/{game_pk}/boxscore")
    # Only team identity and per-player stats are read (spec §5.1); the rest is bulk.
    return {
        "teams": {
            side: {"team": team["team"], "players": team["players"]}
            for side, team in payload["teams"].items()
        }
    }


def _leaders(
    client: httpx.Client, url: str, stats: str, season: int, page_items: int, keep: set[int]
) -> Payload:
    payload = _get(
        client,
        url,
        {
            "pos": "all",
            "stats": stats,
            "lg": "all",
            "qual": "n",
            "season": season,
            "sortDir": "default",
            "sortStat": "WAR",
            "pageItems": page_items,
        },
    )
    rows: list[Payload] = payload["data"]
    payload["data"] = [
        row for i, row in enumerate(rows) if i < PLAYERS or row.get("xMLBAMID") in keep
    ]
    return payload


def _write(path: Path, payload: Payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {path.relative_to(FIXTURES.parent.parent)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record live fixtures.")
    parser.add_argument("--date", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--keep-ids",
        type=lambda s: {int(i) for i in s.split(",") if i.strip()},
        default=set[int](),
        help="comma-separated MLBAM ids to keep in the Fangraphs tables",
    )
    parser.add_argument("--mlb-base", default=_default("mlb_api_base"))
    parser.add_argument("--fangraphs-url", default=_default("fangraphs_api_base"))
    args = parser.parse_args()
    day: date = args.date
    keep: set[int] = args.keep_ids
    season = day.year

    with make_client(args.mlb_base) as mlb:
        matchups = _schedule(mlb, day, "team,broadcasts(all),venue(location),probablePitcher")
        results = _schedule(mlb, day - timedelta(days=1), "team,linescore,decisions")
        standings = _get(
            mlb,
            "/api/v1/standings",
            {
                "leagueId": "103,104",
                "season": season,
                "standingsTypes": "regularSeason",
                "hydrate": "team,division",
            },
        )
        _write(FIXTURES / "mlb" / "schedule_matchups.json", matchups)
        _write(FIXTURES / "mlb" / "schedule_results.json", results)
        _write(FIXTURES / "mlb" / "standings.json", standings)
        for day_entry in results.get("dates", []):
            for game in day_entry["games"]:
                if game["status"]["detailedState"] == "Final":
                    pk = game["gamePk"]
                    _write(FIXTURES / "mlb" / f"boxscore_{pk}.json", _boxscore(mlb, pk))

    # The Fangraphs base is the full endpoint URL, so requests pass it absolutely.
    with make_client(args.fangraphs_url) as fg:
        url = args.fangraphs_url
        _write(
            FIXTURES / "fangraphs" / "batting.json",
            _leaders(fg, url, "bat", season, 25, keep),
        )
        _write(
            FIXTURES / "fangraphs" / "pitching.json",
            _leaders(fg, url, "pit", season, FANGRAPHS_ALL, keep),
        )


if __name__ == "__main__":
    main()
