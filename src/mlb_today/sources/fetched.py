"""Fetch a source, or fall back to its snapshot and say so (spec §4.2, ADR-0002)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from mlb_today.sources.snapshot import Payload, SnapshotStore

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Fetched[T]:
    data: T
    fetched_at: datetime
    stale: bool


class SourceUnavailable(Exception):
    """The source failed and there is no usable snapshot to fall back to."""

    def __init__(self, source: str) -> None:
        super().__init__(f"{source} unavailable and no snapshot to fall back to")
        self.source = source


def fetch_or_snapshot[T](
    source: str,
    fetch_fn: Callable[[], Payload],
    parse_fn: Callable[[Payload], T],
    store: SnapshotStore,
) -> Fetched[T]:
    """Fetch, parse, snapshot, and return fresh data; on any failure, parse the snapshot instead.

    The fresh payload is parsed before it is stored, so a response that does not parse never
    replaces a good snapshot.
    """
    try:
        payload = fetch_fn()
        data = parse_fn(payload)
    except Exception:
        log.warning("source failed, using snapshot", extra={"source": source}, exc_info=True)
    else:
        return Fetched(data, store.put(source, payload), stale=False)

    snapshot = store.get(source)
    if snapshot is None:
        raise SourceUnavailable(source)
    payload, fetched_at = snapshot
    try:
        data = parse_fn(payload)
    except Exception as exc:
        raise SourceUnavailable(source) from exc
    return Fetched(data, fetched_at, stale=True)
