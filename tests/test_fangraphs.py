import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

from mlb_today.sources.fangraphs import FangraphsClient
from mlb_today.sources.models.fangraphs import BatterRaw, PitcherRaw
from mlb_today.sources.snapshot import Payload, SnapshotStore

URL = "https://www.fangraphs.com/api/leaders/major-league/data"
FIXTURES = Path(__file__).parent / "fixtures" / "fangraphs"
MLB_FIXTURES = Path(__file__).parent / "fixtures" / "mlb"


def _fixture(name: str) -> Payload:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path)


@pytest.fixture
def fangraphs(store: SnapshotStore) -> Iterator[FangraphsClient]:
    with httpx.Client(base_url=URL) as client:
        yield FangraphsClient(client, store)


def _pitcher(**fields: object) -> PitcherRaw:
    return PitcherRaw.model_validate(
        {"PlayerName": "Test Pitcher", "TeamNameAbb": "NYY", "xMLBAMID": 1, **fields}
    )


@respx.mock
def test_batting_sends_exact_query_params(fangraphs: FangraphsClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=_fixture("batting")))

    fangraphs.batting(2026)

    assert dict(route.calls.last.request.url.params) == {
        "pos": "all",
        "stats": "bat",
        "lg": "all",
        "qual": "n",
        "season": "2026",
        "sortDir": "default",
        "sortStat": "WAR",
        "pageItems": "25",
    }


@respx.mock
def test_pitching_requests_the_full_table(fangraphs: FangraphsClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=_fixture("pitching")))

    fangraphs.pitching(2026)

    params = dict(route.calls.last.request.url.params)
    assert params.pop("pageItems") == "2000"
    assert params == {
        "pos": "all",
        "stats": "pit",
        "lg": "all",
        "qual": "n",
        "season": "2026",
        "sortDir": "default",
        "sortStat": "WAR",
    }


@respx.mock
def test_requests_the_endpoint_without_a_trailing_slash(fangraphs: FangraphsClient) -> None:
    # Fangraphs 301s `/data/`, and an httpx base URL always ends in a slash.
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=_fixture("batting")))

    fangraphs.batting(2026)

    assert route.calls.last.request.url.path == "/api/leaders/major-league/data"


@respx.mock
def test_batting_parses_fixture_and_snapshots(
    fangraphs: FangraphsClient, store: SnapshotStore
) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json=_fixture("batting")))

    fetched = fangraphs.batting(2026)

    assert fetched.stale is False
    assert store.get("fangraphs.batting") is not None
    assert len(fetched.data) == 25
    top = fetched.data[0]
    assert (top.player_name, top.team, top.mlbam_id) == ("Pete Crow-Armstrong", "CHC", 691718)
    assert top.hr == 45
    assert top.avg == pytest.approx(0.2796, abs=1e-4)
    assert top.ops == pytest.approx(0.9427, abs=1e-4)
    assert top.war == pytest.approx(10.62, abs=1e-2)


@respx.mock
def test_pitching_parses_fixture_including_mlb_fixture_pitchers(
    fangraphs: FangraphsClient, store: SnapshotStore
) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json=_fixture("pitching")))

    fetched = fangraphs.pitching(2026)

    assert store.get("fangraphs.pitching") is not None
    assert len(fetched.data) == 44
    top = fetched.data[0]
    assert (top.player_name, top.team, top.mlbam_id) == ("Jacob Misiorowski", "MIL", 694819)
    assert (top.wins, top.losses, top.saves) == (16, 5, 0)
    assert top.era == pytest.approx(1.80, abs=1e-2)
    assert top.xfip == pytest.approx(2.29, abs=1e-2)
    # Every probable and decision pitcher in the MLB fixtures is in the table.
    matchups = json.loads((MLB_FIXTURES / "schedule_matchups.json").read_text())
    results = json.loads((MLB_FIXTURES / "schedule_results.json").read_text())
    probables = {
        game["teams"][side]["probablePitcher"]["id"]
        for day in matchups["dates"]
        for game in day["games"]
        for side in ("away", "home")
        if "probablePitcher" in game["teams"][side]
    }
    deciders = {
        pitcher["id"]
        for day in results["dates"]
        for game in day["games"]
        for pitcher in game.get("decisions", {}).values()
    }
    assert probables
    assert deciders
    assert probables | deciders <= {p.mlbam_id for p in fetched.data}


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3.21", 3.21), (3.21, 3.21), ("", None), (None, None), ("abc", None), ("nan", None)],
)
def test_rate_stats_coerce_strings_and_default_to_none(
    value: object, expected: float | None
) -> None:
    assert _pitcher(ERA=value).era == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", 12), (12.0, 12), ("12.0", 12), ("", None), (None, None), ("1.5", None)],
)
def test_counting_stats_coerce_to_int_and_default_to_none(
    value: object, expected: int | None
) -> None:
    assert _pitcher(W=value).wins == expected


def test_missing_numeric_fields_default_to_none() -> None:
    batter = BatterRaw.model_validate({"PlayerName": "Test Batter", "TeamNameAbb": "NYY"})

    assert batter.mlbam_id is None
    assert batter.avg is None
    assert batter.hr is None
    assert batter.war is None


@respx.mock
def test_row_with_non_integer_mlbam_id_is_kept(fangraphs: FangraphsClient) -> None:
    payload = _fixture("pitching")
    payload["data"][0]["xMLBAMID"] = "sa3019034"
    payload["data"][1]["ERA"] = "abc"
    respx.get(URL).mock(return_value=httpx.Response(200, json=payload))

    pitchers = fangraphs.pitching(2026).data

    assert len(pitchers) == 44
    assert pitchers[0].player_name == "Jacob Misiorowski"
    assert pitchers[0].mlbam_id is None
    assert pitchers[1].era is None
