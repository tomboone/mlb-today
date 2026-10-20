import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
import respx

from mlb_today.sources.mlb import MlbClient
from mlb_today.sources.models.boxscore import HomeRunRaw
from mlb_today.sources.snapshot import Payload, SnapshotStore

BASE = "https://statsapi.mlb.com"
FIXTURES = Path(__file__).parent / "fixtures" / "mlb"


def _fixture(name: str) -> Payload:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path)


@pytest.fixture
def mlb(store: SnapshotStore) -> Iterator[MlbClient]:
    with httpx.Client(base_url=BASE) as client:
        yield MlbClient(client, store)


@respx.mock
def test_matchups_sends_exact_query_params(mlb: MlbClient) -> None:
    route = respx.get(f"{BASE}/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_fixture("schedule_matchups"))
    )

    mlb.schedule(date(2026, 9, 23), hydrate="matchups")

    assert dict(route.calls.last.request.url.params) == {
        "sportId": "1",
        "startDate": "2026-09-23",
        "endDate": "2026-09-23",
        "timeZone": "America/New_York",
        "sortBy": "gameDate,gameType",
        "hydrate": "team,broadcasts(all),venue(location),probablePitcher",
    }


@respx.mock
def test_results_sends_exact_query_params(mlb: MlbClient) -> None:
    route = respx.get(f"{BASE}/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_fixture("schedule_results"))
    )

    mlb.schedule(date(2026, 9, 22), hydrate="results")

    assert dict(route.calls.last.request.url.params) == {
        "sportId": "1",
        "startDate": "2026-09-22",
        "endDate": "2026-09-22",
        "timeZone": "America/New_York",
        "sortBy": "gameDate,gameType",
        "hydrate": "team,linescore,decisions",
    }


@respx.mock
def test_matchups_parse_teams_probables_venue_and_broadcasts(
    mlb: MlbClient, store: SnapshotStore
) -> None:
    respx.get(f"{BASE}/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_fixture("schedule_matchups"))
    )

    fetched = mlb.schedule(date(2026, 9, 23), hydrate="matchups")

    assert fetched.stale is False
    assert store.get("mlb.schedule.today") is not None
    game = fetched.data.games[0]
    assert game.game_pk == 824223
    assert game.game_date == datetime(2026, 9, 23, 17, 10, tzinfo=UTC)
    away, home = game.teams.away, game.teams.home
    assert (away.team.abbreviation, home.team.abbreviation) == ("WSH", "DET")
    assert (away.league_record.wins, away.league_record.losses) == (75, 84)
    assert (home.league_record.wins, home.league_record.losses) == (74, 85)
    assert away.probable_pitcher is not None
    assert (away.probable_pitcher.id, away.probable_pitcher.full_name) == (
        663992,
        "Richard Lovelady",
    )
    assert home.probable_pitcher is not None
    assert home.probable_pitcher.full_name == "Framber Valdez"
    assert game.venue.name == "Comerica Park"
    assert game.venue.location is not None
    assert (game.venue.location.city, game.venue.location.state_abbrev) == ("Detroit", "MI")
    tv = [(b.call_sign, b.is_national, b.home_away) for b in game.broadcasts if b.type == "TV"]
    assert tv == [("NATS", False, "away"), ("DSN", False, "home")]


@respx.mock
def test_results_parse_linescore_and_decisions(mlb: MlbClient, store: SnapshotStore) -> None:
    respx.get(f"{BASE}/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_fixture("schedule_results"))
    )

    fetched = mlb.schedule(date(2026, 9, 22), hydrate="results")

    assert store.get("mlb.schedule.yesterday") is not None
    game = fetched.data.games[0]
    assert game.status.detailed_state == "Final"
    assert game.linescore is not None
    assert game.linescore.teams is not None
    assert game.linescore.teams.home.runs == 2
    assert (game.linescore.teams.home.hits, game.linescore.teams.home.errors) == (5, 0)
    assert game.decisions is not None
    assert game.decisions.winner is not None
    assert game.decisions.winner.full_name == "Carlos Rodón"
    assert game.decisions.save is not None
    assert (game.decisions.save.id, game.decisions.save.full_name) == (670280, "David Bednar")


@respx.mock
def test_results_parse_extra_innings_postponement_and_doubleheader(mlb: MlbClient) -> None:
    respx.get(f"{BASE}/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_fixture("schedule_results"))
    )

    games = mlb.schedule(date(2026, 9, 22), hydrate="results").data.games

    by_pk = {g.game_pk: g for g in games}
    extra = by_pk[824624]
    assert extra.linescore is not None
    assert extra.linescore.current_inning == 12
    assert [i.num for i in extra.linescore.innings] == list(range(1, 13))
    assert extra.decisions is not None
    assert extra.decisions.winner is not None
    assert extra.decisions.winner.full_name == "Josh Ekness"
    assert extra.decisions.save is None

    postponed = by_pk[824785]
    assert postponed.status.detailed_state == "Postponed"
    assert postponed.linescore is None
    assert postponed.decisions is None

    tb_at_nyy = [g for g in games if g.teams.home.team.abbreviation == "NYY"]
    assert [g.game_pk for g in tb_at_nyy] == [823543, 823494]
    assert {g.teams.away.team.abbreviation for g in tb_at_nyy} == {"TB"}


@respx.mock
def test_empty_dates_parse_to_zero_games(mlb: MlbClient) -> None:
    respx.get(f"{BASE}/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_fixture("schedule_empty"))
    )

    fetched = mlb.schedule(date(2026, 9, 28), hydrate="matchups")

    assert fetched.data.dates == []
    assert fetched.data.games == []


@respx.mock
def test_http_error_falls_back_to_that_hydrations_snapshot(
    mlb: MlbClient, store: SnapshotStore
) -> None:
    snapshot_at = store.put("mlb.schedule.yesterday", _fixture("schedule_results"))
    respx.get(f"{BASE}/api/v1/schedule").mock(return_value=httpx.Response(404))

    fetched = mlb.schedule(date(2026, 9, 22), hydrate="results")

    assert fetched.stale is True
    assert fetched.fetched_at == snapshot_at
    assert len(fetched.data.games) == 5


@respx.mock
def test_boxscore_home_runs_keeps_only_players_who_homered(
    mlb: MlbClient, store: SnapshotStore
) -> None:
    route = respx.get(f"{BASE}/api/v1/game/824222/boxscore").mock(
        return_value=httpx.Response(200, json=_fixture("boxscore_824222"))
    )

    fetched = mlb.boxscore_home_runs(824222)

    assert route.called
    assert fetched.stale is False
    assert store.get("mlb.boxscore.824222") is not None
    # The fixture also holds two players who did not homer, one of whom did not bat at all.
    assert fetched.data == [
        HomeRunRaw(side="away", player_id=682928, name="CJ Abrams", home_runs=2, season_total=33)
    ]


@respx.mock
def test_boxscore_home_runs_tags_the_hitters_side(mlb: MlbClient) -> None:
    respx.get(f"{BASE}/api/v1/game/823543/boxscore").mock(
        return_value=httpx.Response(200, json=_fixture("boxscore_823543"))
    )

    home_runs = mlb.boxscore_home_runs(823543).data

    assert [(hr.side, hr.name, hr.home_runs, hr.season_total) for hr in home_runs] == [
        ("home", "Cody Bellinger", 1, 17)
    ]


@respx.mock
def test_boxscore_without_a_home_run_is_empty(mlb: MlbClient) -> None:
    respx.get(f"{BASE}/api/v1/game/823494/boxscore").mock(
        return_value=httpx.Response(200, json=_fixture("boxscore_823494"))
    )

    assert mlb.boxscore_home_runs(823494).data == []


@respx.mock
def test_boxscore_snapshots_are_kept_per_game(mlb: MlbClient, store: SnapshotStore) -> None:
    snapshot_at = store.put("mlb.boxscore.824222", _fixture("boxscore_824222"))
    store.put("mlb.boxscore.823543", _fixture("boxscore_823543"))
    respx.get(f"{BASE}/api/v1/game/824222/boxscore").mock(return_value=httpx.Response(503))

    fetched = mlb.boxscore_home_runs(824222)

    assert fetched.stale is True
    assert fetched.fetched_at == snapshot_at
    assert [hr.name for hr in fetched.data] == ["CJ Abrams"]


@respx.mock
def test_standings_sends_exact_query_params(mlb: MlbClient, store: SnapshotStore) -> None:
    route = respx.get(f"{BASE}/api/v1/standings").mock(
        return_value=httpx.Response(200, json=_fixture("standings"))
    )

    mlb.standings(2026)

    assert dict(route.calls.last.request.url.params) == {
        "leagueId": "103,104",
        "season": "2026",
        "standingsTypes": "regularSeason",
        "hydrate": "team,division",
    }
    assert store.get("mlb.standings") is not None


@respx.mock
def test_standings_parse_divisions_and_team_records(mlb: MlbClient) -> None:
    respx.get(f"{BASE}/api/v1/standings").mock(
        return_value=httpx.Response(200, json=_fixture("standings"))
    )

    records = mlb.standings(2026).data.records

    assert [(r.league.id, r.division.name_short) for r in records] == [
        (103, "AL East"),
        (103, "AL Central"),
        (103, "AL West"),
        (104, "NL East"),
        (104, "NL Central"),
        (104, "NL West"),
    ]
    assert all(len(r.team_records) == 5 for r in records)
    nyy = records[0].team_records[1]
    assert nyy.team.abbreviation == "NYY"
    assert (nyy.wins, nyy.losses, nyy.winning_percentage) == (93, 68, ".578")
    assert nyy.games_back == "4.5"
    assert nyy.streak is not None
    assert nyy.streak.streak_code == "W1"
    assert nyy.last_ten is not None
    assert (nyy.last_ten.wins, nyy.last_ten.losses) == (5, 5)


@respx.mock
def test_standings_division_leaders_have_games_back_dash(mlb: MlbClient) -> None:
    respx.get(f"{BASE}/api/v1/standings").mock(
        return_value=httpx.Response(200, json=_fixture("standings"))
    )

    records = mlb.standings(2026).data.records

    leaders = [(r.team_records[0].team.abbreviation, r.team_records[0].games_back) for r in records]
    assert leaders == [
        ("TB", "-"),
        ("CLE", "-"),
        ("HOU", "-"),
        ("ATL", "-"),
        ("MIL", "-"),
        ("LAD", "-"),
    ]
