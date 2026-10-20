import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mlb_today.digest.leaderboards import build_batting, build_pitching
from mlb_today.digest.models import LeaderRow
from mlb_today.sources.models.fangraphs import (
    BatterRaw,
    BattingResponse,
    PitcherRaw,
    PitchingResponse,
)
from mlb_today.sources.snapshot import Payload

FIXTURES = Path(__file__).parent / "fixtures"
AS_OF = datetime(2026, 9, 28, 7, 0, tzinfo=UTC)


def _fixture(name: str) -> Payload:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture
def batting() -> list[BatterRaw]:
    return BattingResponse.model_validate(_fixture("fangraphs/batting")).data


@pytest.fixture
def pitching() -> list[PitcherRaw]:
    return PitchingResponse.model_validate(_fixture("fangraphs/pitching")).data


def test_batting_board_carries_its_columns_and_as_of(batting: list[BatterRaw]) -> None:
    board = build_batting(batting, AS_OF)

    top = batting[0]
    assert board.kind == "batting"
    assert board.as_of == AS_OF
    assert board.rows[0] == LeaderRow(
        player=top.player_name, team=top.team, war=top.war, avg=top.avg, hr=top.hr, ops=top.ops
    )


def test_pitching_board_is_the_top_25_by_war(pitching: list[PitcherRaw]) -> None:
    board = build_pitching(list(reversed(pitching)), AS_OF)

    top = max(pitching, key=lambda row: row.war or 0)
    assert board.kind == "pitching"
    assert len(pitching) > 25
    assert len(board.rows) == 25
    assert board.rows[0] == LeaderRow(
        player=top.player_name,
        team=top.team,
        war=top.war,
        wins=top.wins,
        losses=top.losses,
        era=top.era,
        xfip=top.xfip,
    )
    wars = [row.war for row in board.rows]
    assert wars == sorted(wars, key=lambda war: war or 0, reverse=True)


def test_missing_stats_stay_in_the_row_as_none() -> None:
    rows = [BatterRaw.model_validate({"PlayerName": "A", "TeamNameAbb": "TB", "WAR": 1.5})]

    (row,) = build_batting(rows, AS_OF).rows

    assert row == LeaderRow(player="A", team="TB", war=1.5)


def test_row_without_war_sorts_last_rather_than_dropping() -> None:
    rows = [
        BatterRaw.model_validate({"PlayerName": "No WAR", "TeamNameAbb": "TB"}),
        BatterRaw.model_validate({"PlayerName": "Some WAR", "TeamNameAbb": "TB", "WAR": -0.4}),
    ]

    board = build_batting(rows, AS_OF)

    assert [row.player for row in board.rows] == ["Some WAR", "No WAR"]
