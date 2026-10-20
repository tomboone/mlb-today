from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mlb_today.sources.fetched import SourceUnavailable, fetch_or_snapshot
from mlb_today.sources.snapshot import Payload, SnapshotStore


def _games(payload: Payload) -> list[int]:
    return [g["gamePk"] for g in payload["games"]]


def _fails() -> Payload:
    raise httpx.ConnectError("refused")


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path)


def test_success_parses_stores_and_is_fresh(store: SnapshotStore) -> None:
    before = datetime.now(UTC)

    result = fetch_or_snapshot("mlb", lambda: {"games": [{"gamePk": 7}]}, _games, store)

    assert result.data == [7]
    assert result.stale is False
    assert before <= result.fetched_at <= datetime.now(UTC)
    assert store.get("mlb") == ({"games": [{"gamePk": 7}]}, result.fetched_at)


def test_failure_with_snapshot_is_stale_with_snapshot_time(store: SnapshotStore) -> None:
    snapshot_at = store.put("mlb", {"games": [{"gamePk": 3}]})

    result = fetch_or_snapshot("mlb", _fails, _games, store)

    assert result.data == [3]
    assert result.stale is True
    assert result.fetched_at == snapshot_at


def test_failure_without_snapshot_raises_source_unavailable(store: SnapshotStore) -> None:
    with pytest.raises(SourceUnavailable) as excinfo:
        fetch_or_snapshot("mlb", _fails, _games, store)

    assert excinfo.value.source == "mlb"


def test_unparseable_fresh_payload_falls_back_and_keeps_snapshot(store: SnapshotStore) -> None:
    snapshot_at = store.put("mlb", {"games": [{"gamePk": 3}]})

    result = fetch_or_snapshot("mlb", lambda: {"unexpected": True}, _games, store)

    assert result.data == [3]
    assert result.stale is True
    assert store.get("mlb") == ({"games": [{"gamePk": 3}]}, snapshot_at)


def test_unparseable_snapshot_raises_source_unavailable(store: SnapshotStore) -> None:
    store.put("mlb", {"unexpected": True})

    with pytest.raises(SourceUnavailable):
        fetch_or_snapshot("mlb", _fails, _games, store)
