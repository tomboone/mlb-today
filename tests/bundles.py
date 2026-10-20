"""The M3 fixtures as a `SourceBundle`, shared by the digest-build and render tests."""

import json
from datetime import UTC, datetime
from pathlib import Path

from mlb_today.digest.models import SourceBundle
from mlb_today.sources.fetched import Fetched
from mlb_today.sources.models.boxscore import BoxscoreResponse, HomeRunRaw
from mlb_today.sources.models.fangraphs import BattingResponse, PitchingResponse
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.sources.models.standings import StandingsResponse
from mlb_today.sources.snapshot import Payload

FIXTURES = Path(__file__).parent / "fixtures"
BOXSCORE_PKS = (823494, 823543, 824222, 824624)
FETCHED_AT = datetime(2026, 9, 28, 13, 0, tzinfo=UTC)
SNAPSHOT_AT = datetime(2026, 9, 27, 13, 0, tzinfo=UTC)


def _fixture(name: str) -> Payload:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def fresh[T](data: T) -> Fetched[T]:
    return Fetched(data, FETCHED_AT, stale=False)


def schedule(name: str) -> Fetched[ScheduleResponse]:
    return fresh(ScheduleResponse.model_validate(_fixture(f"mlb/{name}")))


def _home_runs(pk: int) -> Fetched[list[HomeRunRaw]]:
    return fresh(BoxscoreResponse.model_validate(_fixture(f"mlb/boxscore_{pk}")).home_runs())


def full_bundle() -> SourceBundle:
    """Every source fetched fresh, with games both today and yesterday."""
    return SourceBundle(
        matchups=schedule("schedule_matchups"),
        results=schedule("schedule_results"),
        home_runs={pk: _home_runs(pk) for pk in BOXSCORE_PKS},
        standings=fresh(StandingsResponse.model_validate(_fixture("mlb/standings"))),
        batting=fresh(BattingResponse.model_validate(_fixture("fangraphs/batting")).data),
        pitching=fresh(PitchingResponse.model_validate(_fixture("fangraphs/pitching")).data),
    )
