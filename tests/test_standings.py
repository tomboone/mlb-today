import json
from pathlib import Path
from typing import Any

import pytest

from mlb_today.digest.models import StandingsRow
from mlb_today.digest.standings import build_standings
from mlb_today.sources.models.standings import StandingsResponse
from mlb_today.sources.snapshot import Payload

FIXTURES = Path(__file__).parent / "fixtures"
DIVISIONS = [
    ("AL", "East"),
    ("AL", "Central"),
    ("AL", "West"),
    ("NL", "East"),
    ("NL", "Central"),
    ("NL", "West"),
]


@pytest.fixture
def payload() -> Payload:
    return json.loads((FIXTURES / "mlb/standings.json").read_text())


def _standings(payload: Payload) -> StandingsResponse:
    return StandingsResponse.model_validate(payload)


def _team(payload: Payload, abbr: str) -> dict[str, Any]:
    return next(
        team
        for record in payload["records"]
        for team in record["teamRecords"]
        if team["team"]["abbreviation"] == abbr
    )


def test_divisions_are_ordered_al_east_to_nl_west(payload: Payload) -> None:
    standings = build_standings(_standings(payload))

    assert [(d.league, d.division) for d in standings] == DIVISIONS


def test_division_order_does_not_depend_on_response_order(payload: Payload) -> None:
    payload["records"].reverse()

    standings = build_standings(_standings(payload))

    assert [(d.league, d.division) for d in standings] == DIVISIONS


def test_leader_row_carries_record_last_ten_and_streak(payload: Payload) -> None:
    al_east = build_standings(_standings(payload))[0]

    assert al_east.rows[0] == StandingsRow(
        abbr="TB", w=98, l=64, pct=".605", gb="-", last_ten="5-5", streak="L1"
    )
    assert al_east.rows[1].gb == "4.5"


def test_rows_are_sorted_by_games_back_whatever_the_response_order(payload: Payload) -> None:
    for record in payload["records"]:
        record["teamRecords"].reverse()

    al_east = build_standings(_standings(payload))[0]

    assert [row.abbr for row in al_east.rows] == ["TB", "NYY", "BOS", "BAL", "TOR"]


def test_rows_tied_on_games_back_put_more_wins_first(payload: Payload) -> None:
    # Unequal schedules: TOR at 80-81 and BAL at 79-82 would both sit 18.5 back.
    _team(payload, "TOR").update(wins=80, losses=81, gamesBack="18.5")
    _team(payload, "BAL").update(gamesBack="18.5")
    al_east = next(r for r in payload["records"] if r["division"]["id"] == 201)
    al_east["teamRecords"].reverse()

    rows = build_standings(_standings(payload))[0].rows

    assert [row.abbr for row in rows][-2:] == ["TOR", "BAL"]


def test_team_without_streak_or_last_ten_shows_a_dash(payload: Payload) -> None:
    tb = _team(payload, "TB")
    del tb["streak"]
    tb["records"]["splitRecords"] = []

    leader = build_standings(_standings(payload))[0].rows[0]

    assert (leader.last_ten, leader.streak) == ("-", "-")


def test_no_records_builds_no_divisions() -> None:
    assert build_standings(StandingsResponse()) == []
