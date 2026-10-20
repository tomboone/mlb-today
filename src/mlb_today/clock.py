"""Time as a dependency, so the scheduler can be tested without waiting."""

import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """The current instant, timezone-aware."""
        ...

    def sleep_until(self, when: datetime) -> None:
        """Block until `when`; return immediately if it has already passed."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep_until(self, when: datetime) -> None:
        while (remaining := (when - self.now()).total_seconds()) > 0:
            time.sleep(remaining)
