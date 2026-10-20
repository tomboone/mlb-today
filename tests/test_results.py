import json
from pathlib import Path
from typing import Any

import pytest

from mlb_today.digest.models import Decision, Decisions, HomeRun, Result, ResultSide
from mlb_today.digest.results import build_results
from mlb_today.sources.models.boxscore import BoxscoreResponse, HomeRunRaw
from mlb_today.sources.models.fangraphs import PitcherRaw, PitchingResponse
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.sources.snapshot import Payload

FIXTURES = Path(__file__).parent / "fixtures"
BOXSCORE_PKS = (823494, 823543, 824222, 824624)
POSTPONED_PK = 824785
EXTRA_INNING_PK = 824624


def _fixture(name: str) -> Payload:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _schedule(payload: Payload) -> ScheduleResponse:
    return ScheduleResponse.model_validate(payload)


def _game(payload: Payload, game_pk: int) -> dict[str, Any]:
    return next(g for g in payload["dates"][0]["games"] if g["gamePk"] == game_pk)


@pytest.fixture
def payload() -> Payload:
    return _fixture("mlb/schedule_results")


@pytest.fixture
def boxscores() -> dict[int, list[HomeRunRaw]]:
    return {
        pk: BoxscoreResponse.model_validate(_fixture(f"mlb/boxscore_{pk}")).home_runs()
        for pk in BOXSCORE_PKS
    }


@pytest.fixture
def pitching() -> list[PitcherRaw]:
    return PitchingResponse.model_validate(_fixture("fangraphs/pitching")).data


def _by_abbrs(results: list[Result], away: str, home: str) -> list[Result]:
    return [r for r in results if (r.away.abbr, r.home.abbr) == (away, home)]


def test_final_nine_inning_game_carries_score_decisions_and_home_runs(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    results = build_results(_schedule(payload), boxscores, pitching)

    (wsh_det,) = _by_abbrs(results, "WSH", "DET")
    assert wsh_det == Result(
        status="Final",
        innings=None,
        away=ResultSide(
            abbr="WSH",
            runs=3,
            hits=7,
            errors=0,
            home_runs=[HomeRun(player="CJ Abrams", season_total=33)],
        ),
        home=ResultSide(abbr="DET", runs=1, hits=7, errors=0, home_runs=[]),
        decisions=Decisions(
            winner=Decision(name="Jackson Kent", wins=2, losses=4),
            loser=Decision(name="Drew Anderson", wins=5, losses=7),
            save=Decision(name="Erik Tolman", saves=5),
        ),
    )


def test_extra_inning_game_reports_its_innings(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    results = build_results(_schedule(payload), boxscores, pitching)

    (mia_chc,) = _by_abbrs(results, "MIA", "CHC")
    assert mia_chc.innings == 12
    assert (mia_chc.away.runs, mia_chc.home.runs) == (8, 2)
    assert mia_chc.away.home_runs == [HomeRun(player="Kyle Stowers", season_total=20)]


def test_ten_inning_game_reports_ten(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    linescore = _game(payload, EXTRA_INNING_PK)["linescore"]
    linescore["currentInning"] = 10
    linescore["innings"] = linescore["innings"][:10]

    (mia_chc,) = _by_abbrs(build_results(_schedule(payload), boxscores, pitching), "MIA", "CHC")

    assert mia_chc.innings == 10


def test_postponed_game_carries_status_and_teams_only(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    results = build_results(_schedule(payload), boxscores, pitching)

    (tor_bal,) = _by_abbrs(results, "TOR", "BAL")
    assert tor_bal == Result(
        status="Postponed",
        innings=None,
        away=ResultSide(abbr="TOR", runs=None, hits=None, errors=None),
        home=ResultSide(abbr="BAL", runs=None, hits=None, errors=None),
        decisions=None,
    )


def test_suspended_game_drops_its_partial_linescore(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    _game(payload, EXTRA_INNING_PK)["status"]["detailedState"] = "Suspended: Rain"

    (mia_chc,) = _by_abbrs(build_results(_schedule(payload), boxscores, pitching), "MIA", "CHC")

    assert mia_chc.status == "Suspended: Rain"
    assert (mia_chc.innings, mia_chc.decisions) == (None, None)
    assert (mia_chc.away.runs, mia_chc.away.hits, mia_chc.away.errors) == (None, None, None)
    assert mia_chc.away.home_runs == []


def test_doubleheader_keeps_both_games_in_first_pitch_order(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    results = build_results(_schedule(payload), boxscores, pitching)

    game_one, game_two = _by_abbrs(results, "TB", "NYY")
    assert (game_one.away.runs, game_one.home.runs) == (0, 2)
    assert game_one.home.home_runs == [HomeRun(player="Cody Bellinger", season_total=17)]
    assert (game_two.away.runs, game_two.home.runs) == (6, 1)
    assert [r.away.abbr for r in results] == ["TB", "TOR", "WSH", "TB", "MIA"]


def test_final_game_without_boxscore_has_no_home_runs(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    del boxscores[824222]

    (wsh_det,) = _by_abbrs(build_results(_schedule(payload), boxscores, pitching), "WSH", "DET")

    assert (wsh_det.away.home_runs, wsh_det.home.home_runs) == ([], [])
    assert wsh_det.away.runs == 3


def test_game_without_save_has_no_save_decision(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    results = build_results(_schedule(payload), boxscores, pitching)

    (mia_chc,) = _by_abbrs(results, "MIA", "CHC")
    assert mia_chc.decisions == Decisions(
        winner=Decision(name="Josh Ekness", wins=3, losses=4),
        loser=Decision(name="Caleb Thielbar", wins=3, losses=4),
        save=None,
    )


def test_pitcher_without_fangraphs_row_has_no_record(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]], pitching: list[PitcherRaw]
) -> None:
    decisions = _game(payload, 824222)["decisions"]
    decisions["winner"]["id"] = 1
    decisions["save"]["id"] = 2

    (wsh_det,) = _by_abbrs(build_results(_schedule(payload), boxscores, pitching), "WSH", "DET")

    assert wsh_det.decisions is not None
    assert wsh_det.decisions.winner == Decision(name="Jackson Kent")
    assert wsh_det.decisions.save == Decision(name="Erik Tolman")


def test_fangraphs_unavailable_leaves_every_record_none(
    payload: Payload, boxscores: dict[int, list[HomeRunRaw]]
) -> None:
    results = build_results(_schedule(payload), boxscores, None)

    (wsh_det,) = _by_abbrs(results, "WSH", "DET")
    assert wsh_det.decisions == Decisions(
        winner=Decision(name="Jackson Kent"),
        loser=Decision(name="Drew Anderson"),
        save=Decision(name="Erik Tolman"),
    )


def test_no_games_yesterday_yields_no_results() -> None:
    assert build_results(_schedule(_fixture("mlb/schedule_empty")), {}, None) == []
