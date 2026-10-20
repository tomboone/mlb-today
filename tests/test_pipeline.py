import logging
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from mlb_today.pipeline import build, send_digest
from mlb_today.settings import Settings
from mlb_today.sources.snapshot import SnapshotStore
from mlb_today.transport.outbox import OutboxTransport
from tests.bundles import BOXSCORE_PKS
from tests.mocked_sources import SOURCES, mock_sources, seed_snapshots

DAY = date(2026, 9, 23)


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_sleep(_seconds: float) -> None:
        pass

    monkeypatch.setattr("mlb_today.sources.http.time.sleep", no_sleep)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.model_validate({"recipients": ["fan@example.com"], "data_dir": tmp_path})


@respx.mock
def test_fetches_every_source_and_box_scores_for_final_games_only(settings: Settings) -> None:
    routes = mock_sources(respx.mock)

    digest, rendered = build(DAY, settings)

    assert all(route.call_count == 1 for route in routes.values())
    # The postponed game in yesterday's schedule has no box score to fetch.
    assert respx.calls.call_count == len(routes)
    assert (digest.kind, digest.stale, digest.unavailable) == ("full", {}, [])
    assert rendered.subject == "MLB Today — Sep 23"


@respx.mock
def test_requests_yesterday_and_the_digest_season(settings: Settings) -> None:
    routes = mock_sources(respx.mock)

    build(date(2027, 1, 1), settings)

    yesterday = routes["mlb.schedule.yesterday"].calls.last.request.url.params
    assert yesterday["startDate"] == "2026-12-31"
    assert routes["mlb.standings"].calls.last.request.url.params["season"] == "2027"
    assert routes["fangraphs.pitching"].calls.last.request.url.params["season"] == "2027"


@respx.mock
def test_fangraphs_503_without_snapshot_still_sends(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    mock_sources(respx.mock)["fangraphs.pitching"].return_value = httpx.Response(503)
    outbox = OutboxTransport(settings.data_dir / "outbox", day=DAY)

    with caplog.at_level(logging.INFO, logger="mlb_today.pipeline"):
        receipt = send_digest(DAY, settings, outbox)

    [sent] = [r for r in caplog.records if r.getMessage() == "digest sent"]
    assert vars(sent)["unavailable"] == ["fangraphs.pitching"]
    assert receipt.transport == "outbox"
    assert "Fangraphs pitching" in (settings.data_dir / "outbox" / "2026-09-23.txt").read_text()


@respx.mock
def test_successful_fetches_leave_snapshots_behind(settings: Settings) -> None:
    mock_sources(respx.mock)

    build(DAY, settings)

    store = SnapshotStore(settings.data_dir)
    assert store.get("fangraphs.batting") is not None
    assert all(store.get(f"mlb.boxscore.{pk}") is not None for pk in BOXSCORE_PKS)


def test_offline_reads_snapshots_and_makes_no_http_calls(settings: Settings) -> None:
    seed_snapshots(SnapshotStore(settings.data_dir))

    with respx.mock(assert_all_called=False) as router:
        anything = router.route().mock(return_value=httpx.Response(500))
        digest, _ = build(DAY, settings, offline=True)

    assert anything.call_count == 0
    assert digest.kind == "full"
    assert digest.unavailable == []
    assert digest.results
    assert set(digest.stale) == set(SOURCES)


def test_offline_without_snapshots_builds_a_digest_saying_so(settings: Settings) -> None:
    with respx.mock(assert_all_called=False) as router:
        anything = router.route().mock(return_value=httpx.Response(500))
        digest, _ = build(DAY, settings, offline=True)

    assert anything.call_count == 0
    assert digest.kind == "scores_only"
    assert digest.unavailable == [
        "mlb.schedule.today",
        "mlb.schedule.yesterday",
        "mlb.standings",
        "fangraphs.batting",
        "fangraphs.pitching",
    ]
