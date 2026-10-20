import threading
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from mlb_today.scheduler import NOTHING, REPLAN_DELAY, RETRY_DELAY, Plan, Scheduler, plan
from mlb_today.settings import Settings
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.state import Marker, State
from mlb_today.transport.base import AllTransportsFailed, SendReceipt, TransportError
from tests.fakes import FakeClock

ET = ZoneInfo("America/New_York")
DAY = date(2026, 9, 23)
YESTERDAY = DAY - timedelta(days=1)
NO_GAMES = ScheduleResponse()


def at(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=ET)


def _team(team_id: int, abbreviation: str) -> dict[str, Any]:
    return {
        "team": {"id": team_id, "name": abbreviation, "abbreviation": abbreviation},
        "leagueRecord": {"wins": 80, "losses": 70},
    }


def schedule(*first_pitches: datetime) -> ScheduleResponse:
    """A schedule with one game per first pitch, in MLB's UTC `gameDate` form."""
    games = [
        {
            "gamePk": pk,
            "gameDate": first_pitch.astimezone(UTC).isoformat(),
            "status": {"detailedState": "Scheduled"},
            "teams": {"away": _team(147, "NYY"), "home": _team(111, "BOS")},
            "venue": {"id": 3, "name": "Fenway Park"},
        }
        for pk, first_pitch in enumerate(first_pitches, start=1)
    ]
    return ScheduleResponse.model_validate({"dates": [{"games": games}]})


class StubPipeline:
    """Schedules by date, and a send that records when it ran and fails the first `failures`."""

    def __init__(
        self, clock: FakeClock, schedules: dict[date, ScheduleResponse | None], failures: int = 0
    ) -> None:
        self.clock = clock
        self.by_date = schedules
        self.failures = failures
        self.sends: list[datetime] = []

    def schedules(self, day: date) -> tuple[ScheduleResponse | None, ScheduleResponse | None]:
        yesterday = day - timedelta(days=1)
        return self.by_date.get(day, NO_GAMES), self.by_date.get(yesterday, NO_GAMES)

    def send(self, day: date) -> SendReceipt:
        self.sends.append(self.clock.now())
        if self.failures:
            self.failures -= 1
            raise AllTransportsFailed([("resend", TransportError("503"))])
        return SendReceipt(transport="resend", message_id=f"msg-{day}", sent_at=self.clock.now())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.model_validate({"recipients": ["fan@example.com"], "data_dir": tmp_path})


@pytest.fixture
def state(settings: Settings) -> State:
    return State(settings.data_dir / "state.json")


def scheduler(
    clock: FakeClock,
    state: State,
    settings: Settings,
    pipeline: StubPipeline,
    stop: threading.Event | None = None,
) -> Scheduler:
    return Scheduler(clock, state, settings, pipeline, stop=stop)


# plan()


def test_plan_game_day_sends_lead_minutes_before_the_earliest_first_pitch(
    settings: Settings,
) -> None:
    today = schedule(at(19, 5), at(13, 5), at(16, 10))

    assert plan(DAY, today, NO_GAMES, settings) == Plan(kind="full", send_at=at(12, 35))


def test_plan_honours_send_lead_minutes(settings: Settings) -> None:
    settings = settings.model_copy(update={"send_lead_minutes": 45})

    assert plan(DAY, schedule(at(13, 5)), NO_GAMES, settings).send_at == at(12, 20)


def test_plan_early_international_game_sends_before_dawn(settings: Settings) -> None:
    assert plan(DAY, schedule(at(6, 10)), NO_GAMES, settings) == Plan("full", at(5, 40))


def test_plan_day_after_a_game_day_is_scores_only(settings: Settings) -> None:
    yesterday = schedule(at(19, 5, YESTERDAY))

    assert plan(DAY, NO_GAMES, yesterday, settings) == Plan("scores_only", at(9, 0))


def test_plan_no_games_either_day_is_nothing(settings: Settings) -> None:
    assert plan(DAY, NO_GAMES, NO_GAMES, settings) == NOTHING


def test_plan_unknown_today_is_nothing_even_after_a_game_day(settings: Settings) -> None:
    assert plan(DAY, None, schedule(at(19, 5, YESTERDAY)), settings) == NOTHING


def test_plan_unknown_yesterday_on_a_no_game_day_is_nothing(settings: Settings) -> None:
    assert plan(DAY, NO_GAMES, None, settings) == NOTHING


# Scheduler


def test_boot_before_send_time_sends_once_at_send_time(state: State, settings: Settings) -> None:
    clock = FakeClock(at(10))
    pipeline = StubPipeline(clock, {DAY: schedule(at(13, 5))})

    scheduler(clock, state, settings, pipeline).cycle()

    assert pipeline.sends == [at(12, 35)]
    marker = state.read()
    assert marker is not None
    assert (marker.date, marker.kind, marker.transport) == (DAY, "full", "resend")
    assert (marker.sent_at, marker.planned_at) == (at(12, 35), at(10))
    # Then it sleeps until the next day's plan.
    assert clock.now() == at(3, 0, DAY + timedelta(days=1))

    # A restart later the same day finds the marker and does not send again.
    clock.current = at(12, 40)
    scheduler(clock, state, settings, pipeline).cycle()
    assert pipeline.sends == [at(12, 35)]


def test_boot_after_send_time_with_todays_marker_does_not_send(
    state: State, settings: Settings
) -> None:
    sent = Marker(date=DAY, kind="full", sent_at=at(12, 35), transport="resend", message_id="m")
    state.write(sent)
    clock = FakeClock(at(14))
    pipeline = StubPipeline(clock, {DAY: schedule(at(13, 5))})

    scheduler(clock, state, settings, pipeline).cycle()

    assert pipeline.sends == []
    assert state.read() == sent.model_copy(update={"planned_at": at(14)})


def test_boot_after_send_time_without_marker_sends_immediately(
    state: State, settings: Settings
) -> None:
    state.write(Marker(date=YESTERDAY, kind="full", sent_at=at(12, 35, YESTERDAY)))
    clock = FakeClock(at(14))
    pipeline = StubPipeline(clock, {DAY: schedule(at(13, 5))})

    scheduler(clock, state, settings, pipeline).cycle()

    assert pipeline.sends == [at(14)]
    marker = state.read()
    assert marker is not None
    assert marker.date == DAY


def test_no_games_today_after_a_game_day_sends_scores_only_at_nine(
    state: State, settings: Settings
) -> None:
    clock = FakeClock(at(3))
    pipeline = StubPipeline(clock, {YESTERDAY: schedule(at(19, 5, YESTERDAY))})

    scheduler(clock, state, settings, pipeline).cycle()

    assert pipeline.sends == [at(9)]
    marker = state.read()
    assert marker is not None
    assert (marker.date, marker.kind) == (DAY, "scores_only")


def test_no_games_either_day_sleeps_until_the_next_plan(state: State, settings: Settings) -> None:
    clock = FakeClock(at(3))
    pipeline = StubPipeline(clock, {})

    scheduler(clock, state, settings, pipeline).cycle()

    assert pipeline.sends == []
    assert clock.sleeps == [at(3, 0, DAY + timedelta(days=1))]
    assert state.read() == Marker(planned_at=at(3))


def test_unavailable_schedule_sends_nothing_and_plans_again_soon(
    state: State, settings: Settings
) -> None:
    clock = FakeClock(at(3))
    pipeline = StubPipeline(clock, {DAY: None, YESTERDAY: schedule(at(19, 5, YESTERDAY))})

    scheduler(clock, state, settings, pipeline).cycle()

    assert pipeline.sends == []
    assert clock.sleeps == [at(3) + REPLAN_DELAY]


def test_unavailable_yesterday_on_a_no_game_day_plans_again_soon(
    state: State, settings: Settings
) -> None:
    clock = FakeClock(at(3))
    pipeline = StubPipeline(clock, {YESTERDAY: None})

    scheduler(clock, state, settings, pipeline).cycle()

    assert clock.sleeps == [at(3) + REPLAN_DELAY]


def test_outage_at_plan_time_delays_the_digest_rather_than_skipping_it(
    state: State, settings: Settings
) -> None:
    clock = FakeClock(at(3))
    pipeline = StubPipeline(clock, {DAY: None})
    loop = scheduler(clock, state, settings, pipeline)

    loop.cycle()
    pipeline.by_date[DAY] = schedule(at(13, 5))
    loop.cycle()

    assert pipeline.sends == [at(12, 35)]


def test_replan_never_overshoots_the_next_plan_time(state: State, settings: Settings) -> None:
    clock = FakeClock(at(2, 50))
    pipeline = StubPipeline(clock, {DAY: None})

    scheduler(clock, state, settings, pipeline).cycle()

    assert clock.sleeps == [at(3)]


def test_early_international_game_plan_sleeps_two_hours_forty(
    state: State, settings: Settings
) -> None:
    clock = FakeClock(at(3))
    pipeline = StubPipeline(clock, {DAY: schedule(at(6, 10))})

    scheduler(clock, state, settings, pipeline).cycle()

    assert clock.sleeps[0] - at(3) == timedelta(hours=2, minutes=40)
    assert pipeline.sends == [at(5, 40)]


def test_boot_before_plan_time_replans_at_plan_time(state: State, settings: Settings) -> None:
    clock = FakeClock(at(1))
    pipeline = StubPipeline(clock, {})

    scheduler(clock, state, settings, pipeline).cycle()

    assert clock.sleeps == [at(3)]


def test_transport_failure_leaves_the_marker_and_retries_once(
    state: State, settings: Settings
) -> None:
    clock = FakeClock(at(10))
    pipeline = StubPipeline(clock, {DAY: schedule(at(13, 5))}, failures=2)

    scheduler(clock, state, settings, pipeline).cycle()

    assert pipeline.sends == [at(12, 35), at(12, 35) + RETRY_DELAY]
    # Only the plan touched the file; nothing records a send.
    assert state.read() == Marker(planned_at=at(10))


def test_transport_failure_then_successful_retry_writes_the_marker(
    state: State, settings: Settings
) -> None:
    clock = FakeClock(at(10))
    pipeline = StubPipeline(clock, {DAY: schedule(at(13, 5))}, failures=1)

    scheduler(clock, state, settings, pipeline).cycle()

    marker = state.read()
    assert marker is not None
    assert (marker.date, marker.sent_at) == (DAY, at(12, 45))


def test_run_forever_returns_once_stopped(state: State, settings: Settings) -> None:
    stop = threading.Event()
    stop.set()
    clock = FakeClock(at(10))
    pipeline = StubPipeline(clock, {DAY: schedule(at(13, 5))})

    scheduler(clock, state, settings, pipeline, stop).run_forever()

    assert (pipeline.sends, state.read()) == ([], None)


def test_stop_during_a_send_finishes_it_and_records_the_marker(
    state: State, settings: Settings
) -> None:
    stop = threading.Event()
    clock = FakeClock(at(10))

    class StoppingPipeline(StubPipeline):
        def send(self, day: date) -> SendReceipt:
            stop.set()
            return super().send(day)

    pipeline = StoppingPipeline(clock, {DAY: schedule(at(13, 5))})

    scheduler(clock, state, settings, pipeline, stop).run_forever()

    assert pipeline.sends == [at(12, 35)]
    marker = state.read()
    assert marker is not None
    assert marker.date == DAY


def test_stop_before_send_time_skips_the_send(state: State, settings: Settings) -> None:
    stop = threading.Event()
    clock = FakeClock(at(10))

    class StoppingPipeline(StubPipeline):
        def schedules(self, day: date) -> tuple[ScheduleResponse | None, ScheduleResponse | None]:
            stop.set()
            return super().schedules(day)

    pipeline = StoppingPipeline(clock, {DAY: schedule(at(13, 5))})

    scheduler(clock, state, settings, pipeline, stop).run_forever()

    assert pipeline.sends == []
