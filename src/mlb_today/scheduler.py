"""The daily loop: plan the send time, sleep until it, send once (spec §4.2-4.3, ADR-0001)."""

import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from mlb_today.clock import Clock
from mlb_today.digest.models import DigestKind
from mlb_today.settings import Settings
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.state import Marker, State
from mlb_today.transport.base import SendReceipt, TransportError

log = logging.getLogger(__name__)

RETRY_DELAY = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class Plan:
    """What to send on one day and when; both `None` on a day with nothing to send."""

    kind: DigestKind | None
    send_at: datetime | None


NOTHING = Plan(kind=None, send_at=None)


class Pipeline(Protocol):
    def schedules(self, day: date) -> tuple[ScheduleResponse | None, ScheduleResponse | None]:
        """The schedules for `day` and the day before; `None` where one is unavailable."""
        ...

    def send(self, day: date) -> SendReceipt:
        """Build and send the digest for `day`; raises `TransportError` if nothing delivered it."""
        ...


def plan(
    day: date,
    schedule_today: ScheduleResponse | None,
    schedule_yesterday: ScheduleResponse | None,
    settings: Settings,
) -> Plan:
    """A full digest at the earliest first pitch - `SEND_LEAD_MINUTES` on a game day; a scores-only
    digest at `SCORES_ONLY_TIME` local on the day after one; otherwise nothing.

    An unavailable `schedule_today` plans nothing: guessing would either skip a game day or send a
    scores-only digest on one.
    """
    if schedule_today is None:
        return NOTHING
    if games := schedule_today.games:
        first_pitch = min(game.game_date for game in games)
        send_at = first_pitch - timedelta(minutes=settings.send_lead_minutes)
        return Plan(kind="full", send_at=send_at.astimezone(settings.tz_local))
    if schedule_yesterday is not None and schedule_yesterday.games:
        send_at = datetime.combine(day, settings.scores_only_time, tzinfo=settings.tz_local)
        return Plan(kind="scores_only", send_at=send_at)
    return NOTHING


class Scheduler:
    """Plans at boot and at every `PLAN_TIME`, and sends each day's digest at most once.

    The marker in `state` is what makes "at most once" survive a restart: a send time that has
    already passed fires only if the marker does not cover today. Setting `stop` ends the loop at
    the next sleep; a send already under way finishes and records its marker first.
    """

    def __init__(
        self,
        clock: Clock,
        state: State,
        settings: Settings,
        pipeline: Pipeline,
        *,
        stop: threading.Event | None = None,
    ) -> None:
        self._clock = clock
        self._state = state
        self._settings = settings
        self._pipeline = pipeline
        self._stop = stop or threading.Event()

    def run_forever(self) -> None:
        while not self._stop.is_set():
            self.cycle()

    def cycle(self) -> None:
        """Plan today, send if a send is due, then sleep until the next `PLAN_TIME`."""
        now = self._clock.now()
        today = now.astimezone(self._settings.tz_local).date()
        day_plan = plan(today, *self._pipeline.schedules(today), self._settings)
        self._state.touch_planned(now)
        log.info(
            "planned",
            extra={"date": today.isoformat(), "kind": day_plan.kind, "send_at": day_plan.send_at},
        )
        if day_plan.kind is not None and day_plan.send_at is not None:
            self._dispatch(today, day_plan.kind, day_plan.send_at)
        self._sleep_until(self._next_plan_time())

    def _dispatch(self, day: date, kind: DigestKind, send_at: datetime) -> None:
        marker = self._state.read()
        if marker is not None and marker.date == day:
            log.info("already sent today, skipping", extra={"date": day.isoformat()})
            return
        if not self._sleep_until(send_at) or self._send(day, kind):
            return
        log.warning("retrying send", extra={"date": day.isoformat(), "in": str(RETRY_DELAY)})
        if self._sleep_until(self._clock.now() + RETRY_DELAY) and not self._send(day, kind):
            log.error(
                "send failed twice, giving up until the next plan",
                extra={"date": day.isoformat()},
            )

    def _send(self, day: date, kind: DigestKind) -> bool:
        """Send the digest for `day` and record it in the marker; False if nothing delivered it.

        A failed send leaves the marker alone, so a restart will try again (spec §4.2).
        """
        try:
            receipt = self._pipeline.send(day)
        except TransportError as exc:
            log.error("send failed", extra={"date": day.isoformat(), "error": str(exc)})
            return False
        previous = self._state.read()
        self._state.write(
            Marker(
                date=day,
                kind=kind,
                sent_at=receipt.sent_at,
                transport=receipt.transport,
                message_id=receipt.message_id,
                planned_at=previous.planned_at if previous else None,
            )
        )
        return True

    def _sleep_until(self, when: datetime) -> bool:
        """Sleep until `when`; False if `stop` was set, meaning the loop should wind down."""
        self._clock.sleep_until(when)
        return not self._stop.is_set()

    def _next_plan_time(self) -> datetime:
        tz = self._settings.tz_local
        now = self._clock.now().astimezone(tz)
        candidate = datetime.combine(now.date(), self._settings.plan_time, tzinfo=tz)
        if candidate <= now:
            candidate = datetime.combine(
                now.date() + timedelta(days=1), self._settings.plan_time, tzinfo=tz
            )
        return candidate
