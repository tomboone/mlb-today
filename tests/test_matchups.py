import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from mlb_today.digest.matchups import build_matchups
from mlb_today.digest.models import Broadcasts, PitcherLine, Probable
from mlb_today.sources.models.fangraphs import PitcherRaw, PitchingResponse
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.sources.snapshot import Payload

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> Payload:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _schedule(payload: Payload) -> ScheduleResponse:
    return ScheduleResponse.model_validate(payload)


def _games(payload: Payload) -> list[dict[str, Any]]:
    return payload["dates"][0]["games"]


@pytest.fixture
def payload() -> Payload:
    return _fixture("mlb/schedule_matchups")


@pytest.fixture
def pitching() -> list[PitcherRaw]:
    return PitchingResponse.model_validate(_fixture("fangraphs/pitching")).data


def _tv(**fields: object) -> dict[str, object]:
    return {"type": "TV", "name": "Test TV", **fields}


def test_builds_one_matchup_per_game_from_fixture(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    matchups = build_matchups(_schedule(payload), pitching)

    assert len(matchups) == 3
    first = matchups[0]
    assert first.first_pitch == datetime(2026, 9, 23, 17, 10, tzinfo=UTC)
    assert first.status == "Final"
    assert (first.away.abbr, first.away.wins, first.away.losses) == ("WSH", 75, 84)
    assert (first.home.abbr, first.home.wins, first.home.losses) == ("DET", 74, 85)
    assert first.venue == "Comerica Park, Detroit, MI"
    assert first.away.probable == Probable(
        name="Richard Lovelady",
        line=PitcherLine(
            w=3, l=4, era=4.114287059550822, xfip=5.194912186750987, war=-0.5182693302631378
        ),
    )
    assert first.home.probable.name == "Framber Valdez"
    assert first.home.probable.line is not None
    assert (first.home.probable.line.w, first.home.probable.line.l) == (10, 12)


def test_fixture_broadcasts_are_tv_only_split_home_and_away(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    first = build_matchups(_schedule(payload), pitching)[0]

    assert first.tv == Broadcasts(home=["DSN"], away=["NATS"])


def test_absent_probable_is_tbd_with_no_line(payload: Payload, pitching: list[PitcherRaw]) -> None:
    del _games(payload)[0]["teams"]["home"]["probablePitcher"]

    first = build_matchups(_schedule(payload), pitching)[0]

    assert first.home.probable == Probable(name="TBD", line=None)


def test_probable_without_fangraphs_row_has_no_line(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    _games(payload)[0]["teams"]["away"]["probablePitcher"]["id"] = 1

    first = build_matchups(_schedule(payload), pitching)[0]

    assert first.away.probable == Probable(name="Richard Lovelady", line=None)


def test_fangraphs_unavailable_leaves_every_line_none(payload: Payload) -> None:
    matchups = build_matchups(_schedule(payload), None)

    assert all(m.away.probable.line is None and m.home.probable.line is None for m in matchups)
    assert matchups[0].away.probable.name == "Richard Lovelady"


def test_uncoerced_fangraphs_stats_stay_none_not_zero(payload: Payload) -> None:
    pitcher = PitcherRaw.model_validate(
        {"PlayerName": "Richard Lovelady", "TeamNameAbb": "WSH", "xMLBAMID": 663992, "ERA": ""}
    )

    first = build_matchups(_schedule(payload), [pitcher])[0]

    assert first.away.probable.line == PitcherLine(w=None, l=None, era=None, xfip=None, war=None)


def test_national_broadcast_wins_over_its_home_away_tag(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    _games(payload)[0]["broadcasts"] = [
        _tv(callSign="FOX", isNational=True, homeAway="home"),
        _tv(callSign="FOX", isNational=False, homeAway="away"),
        _tv(callSign="DSN", isNational=False, homeAway="home"),
    ]

    first = build_matchups(_schedule(payload), pitching)[0]

    assert first.tv == Broadcasts(national=["FOX"], home=["DSN"])


def test_tv_broadcast_with_neither_national_nor_home_away_is_misc(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    _games(payload)[0]["broadcasts"] = [
        _tv(callSign="MLBN", isNational=False),
        _tv(name="MLB.TV"),
        {"type": "AM", "name": "Radio", "callSign": "WXYZ", "isNational": False},
    ]

    first = build_matchups(_schedule(payload), pitching)[0]

    assert first.tv == Broadcasts(misc=["MLBN", "MLB.TV"])


def test_doubleheader_is_ordered_by_first_pitch(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    _games(payload).reverse()

    matchups = build_matchups(_schedule(payload), pitching)

    assert [m.away.probable.name for m in matchups] == [
        "Richard Lovelady",
        "Max Scherzer",
        "CJ Van Eyk",
    ]


def test_same_first_pitch_is_ordered_by_game_pk(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    games = _games(payload)
    # The doubleheader's two games, 824785 then 824784 in the fixture, at the same instant.
    games[2]["gameDate"] = games[1]["gameDate"]

    matchups = build_matchups(_schedule(payload), pitching)

    assert [m.away.probable.name for m in matchups[1:]] == ["CJ Van Eyk", "Max Scherzer"]


def test_no_game_day_has_no_matchups(pitching: list[PitcherRaw]) -> None:
    assert build_matchups(_schedule(_fixture("mlb/schedule_empty")), pitching) == []


def test_venue_without_location_is_just_the_name(
    payload: Payload, pitching: list[PitcherRaw]
) -> None:
    del _games(payload)[0]["venue"]["location"]

    assert build_matchups(_schedule(payload), pitching)[0].venue == "Comerica Park"
