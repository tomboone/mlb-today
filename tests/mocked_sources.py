"""Every source the pipeline fetches, answered from the recorded fixtures: as respx routes, or
seeded into a snapshot store."""

import json
from pathlib import Path

import httpx
import respx

from mlb_today.sources.mlb import HYDRATE
from mlb_today.sources.snapshot import SnapshotStore
from tests.bundles import BOXSCORE_PKS

FIXTURES = Path(__file__).parent / "fixtures"
MLB = "https://statsapi.mlb.com"
FANGRAPHS = "https://www.fangraphs.com/api/leaders/major-league/data"


# Snapshot source name → fixture.
SOURCES = {
    "mlb.schedule.today": "mlb/schedule_matchups",
    "mlb.schedule.yesterday": "mlb/schedule_results",
    "mlb.standings": "mlb/standings",
    "fangraphs.batting": "fangraphs/batting",
    "fangraphs.pitching": "fangraphs/pitching",
} | {f"mlb.boxscore.{pk}": f"mlb/boxscore_{pk}" for pk in BOXSCORE_PKS}


def _ok(name: str) -> httpx.Response:
    return httpx.Response(200, json=json.loads((FIXTURES / f"{name}.json").read_text()))


def seed_snapshots(store: SnapshotStore) -> None:
    for source, fixture in SOURCES.items():
        store.put(source, json.loads((FIXTURES / f"{fixture}.json").read_text()))


def mock_sources(router: respx.MockRouter) -> dict[str, respx.Route]:
    """One route per source, keyed by its snapshot name; set a route's `return_value` to fail it."""
    routes = {
        "mlb.schedule.today": router.get(
            f"{MLB}/api/v1/schedule", params__contains={"hydrate": HYDRATE["matchups"]}
        ).mock(return_value=_ok("mlb/schedule_matchups")),
        "mlb.schedule.yesterday": router.get(
            f"{MLB}/api/v1/schedule", params__contains={"hydrate": HYDRATE["results"]}
        ).mock(return_value=_ok("mlb/schedule_results")),
        "mlb.standings": router.get(f"{MLB}/api/v1/standings").mock(
            return_value=_ok("mlb/standings")
        ),
        "fangraphs.batting": router.get(FANGRAPHS, params__contains={"stats": "bat"}).mock(
            return_value=_ok("fangraphs/batting")
        ),
        "fangraphs.pitching": router.get(FANGRAPHS, params__contains={"stats": "pit"}).mock(
            return_value=_ok("fangraphs/pitching")
        ),
    }
    for pk in BOXSCORE_PKS:
        routes[f"mlb.boxscore.{pk}"] = router.get(f"{MLB}/api/v1/game/{pk}/boxscore").mock(
            return_value=_ok(f"mlb/boxscore_{pk}")
        )
    return routes
