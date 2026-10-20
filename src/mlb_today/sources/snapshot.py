"""Source snapshots: the last good raw response per source, kept on the data volume (ADR-0002)."""

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

type Payload = dict[str, Any]

log = logging.getLogger(__name__)


class SnapshotStore:
    """Files `<root>/snapshots/<source>.json`, each `{"fetched_at": <iso>, "payload": {...}}`."""

    def __init__(self, root: Path) -> None:
        self._dir = root / "snapshots"

    def _path(self, source: str) -> Path:
        return self._dir / f"{source}.json"

    def get(self, source: str) -> tuple[Payload, datetime] | None:
        """The stored payload and when it was fetched, or None if there is no usable snapshot."""
        path = self._path(source)
        try:
            stored = json.loads(path.read_text())
            return stored["payload"], datetime.fromisoformat(stored["fetched_at"])
        except FileNotFoundError:
            return None
        except (ValueError, KeyError, TypeError):
            log.warning("unreadable snapshot", extra={"source": source, "path": str(path)})
            return None

    def put(self, source: str, payload: Payload) -> datetime:
        """Store `payload` as the latest snapshot, atomically; return the `fetched_at` recorded."""
        fetched_at = datetime.now(UTC)
        body = json.dumps({"fetched_at": fetched_at.isoformat(), "payload": payload})
        self._dir.mkdir(parents=True, exist_ok=True)
        # Write beside the target and rename over it, so a crash never leaves a torn file.
        fd, tmp = tempfile.mkstemp(dir=self._dir, prefix=f".{source}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(body)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path(source))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return fetched_at
