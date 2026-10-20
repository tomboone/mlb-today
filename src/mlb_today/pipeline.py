"""One digest, end to end: fetch every source → build → render → send (spec §4.2 step 2)."""

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import date, timedelta

from mlb_today.digest.build import build_digest
from mlb_today.digest.models import Digest, SourceBundle
from mlb_today.digest.results import FINAL_PREFIXES
from mlb_today.render.render import Rendered, render
from mlb_today.settings import Settings
from mlb_today.sources.fangraphs import FangraphsClient
from mlb_today.sources.fetched import Fetched, SourceUnavailable
from mlb_today.sources.http import make_client
from mlb_today.sources.mlb import MlbClient
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.sources.snapshot import SnapshotStore
from mlb_today.transport.base import Message, SendReceipt, Transport

log = logging.getLogger(__name__)


def fetch_bundle(day: date, mlb: MlbClient, fangraphs: FangraphsClient) -> SourceBundle:
    """Every source the digest for `day` needs, each fresh or from its snapshot.

    A source with no snapshot either is logged and left `None`, so its section is omitted rather
    than the digest failing. Box scores are fetched for yesterday's final games only.
    """
    season = day.year
    results = _available(lambda: mlb.schedule(day - timedelta(days=1), hydrate="results"))
    finals = (
        []
        if results is None
        else [
            g.game_pk
            for g in results.data.games
            if g.status.detailed_state.startswith(FINAL_PREFIXES)
        ]
    )
    return SourceBundle(
        matchups=_available(lambda: mlb.schedule(day, hydrate="matchups")),
        results=results,
        home_runs={pk: _available(lambda pk=pk: mlb.boxscore_home_runs(pk)) for pk in finals},
        standings=_available(lambda: mlb.standings(season)),
        batting=_available(lambda: fangraphs.batting(season)),
        pitching=_available(lambda: fangraphs.pitching(season)),
    )


def build(day: date, settings: Settings, *, offline: bool = False) -> tuple[Digest, Rendered]:
    """The digest for `day` and its rendering; `offline` reads snapshots only, with no network."""
    with _clients(settings, offline=offline) as (mlb, fangraphs):
        bundle = fetch_bundle(day, mlb, fangraphs)
    digest = build_digest(day, bundle)
    return digest, render(digest)


def send_digest(day: date, settings: Settings, transport: Transport) -> SendReceipt:
    """Build the digest for `day` and send it to `RECIPIENTS`; the transport's receipt.

    Raises `TransportError` (`AllTransportsFailed` from a chain) when nothing delivered it.
    """
    digest, rendered = build(day, settings)
    message = Message(
        subject=rendered.subject,
        html=rendered.html,
        text=rendered.text,
        to=settings.recipients,
        # Every real transport sends from its own configured sender; this is informational.
        from_=settings.resend_from or settings.smtp_sender_address or "",
    )
    receipt = transport.send(message)
    log.info(
        "digest sent",
        extra={
            "date": day.isoformat(),
            "kind": digest.kind,
            "stale": sorted(digest.stale),
            "unavailable": digest.unavailable,
            "transport": receipt.transport,
            "message_id": receipt.message_id,
        },
    )
    return receipt


class DigestPipeline:
    """The pipeline as the scheduler drives it: the schedules a plan needs, and a send."""

    def __init__(self, settings: Settings, transport: Transport) -> None:
        self._settings = settings
        self._transport = transport

    def schedules(self, day: date) -> tuple[ScheduleResponse | None, ScheduleResponse | None]:
        """The schedules for `day` and the day before, each fresh or from a snapshot taken today.

        A source's snapshot is whatever it last fetched, so one taken on an earlier day describes
        an earlier day's games; it counts as unavailable rather than as today's schedule.
        """
        with _clients(self._settings, offline=False) as (mlb, _):
            today = _available(lambda: mlb.schedule(day, hydrate="matchups"))
            yesterday = _available(lambda: mlb.schedule(day - timedelta(days=1), hydrate="results"))
        return self._taken_on(day, today), self._taken_on(day, yesterday)

    def send(self, day: date) -> SendReceipt:
        return send_digest(day, self._settings, self._transport)

    def _taken_on(
        self, day: date, fetched: Fetched[ScheduleResponse] | None
    ) -> ScheduleResponse | None:
        if fetched is None:
            return None
        if fetched.stale and fetched.fetched_at.astimezone(self._settings.tz_local).date() != day:
            log.error(
                "schedule snapshot is from another day",
                extra={"date": day.isoformat(), "fetched_at": fetched.fetched_at.isoformat()},
            )
            return None
        return fetched.data


def _available[T](fetch: Callable[[], Fetched[T]]) -> Fetched[T] | None:
    try:
        return fetch()
    except SourceUnavailable as exc:
        log.error("source unavailable", extra={"source": exc.source})
        return None


@contextmanager
def _clients(settings: Settings, *, offline: bool) -> Generator[tuple[MlbClient, FangraphsClient]]:
    store = SnapshotStore(settings.data_dir)
    if offline:
        yield MlbClient(None, store), FangraphsClient(None, store)
        return
    with (
        make_client(settings.mlb_api_base) as mlb_http,
        make_client(settings.fangraphs_api_base) as fangraphs_http,
    ):
        yield MlbClient(mlb_http, store), FangraphsClient(fangraphs_http, store)
