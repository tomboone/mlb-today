"""Every fetched source → the digest (spec §4.2, §6). Pure: no I/O."""

from datetime import date, datetime
from typing import Any

from mlb_today.digest.leaderboards import build_batting, build_pitching
from mlb_today.digest.matchups import build_matchups
from mlb_today.digest.models import Digest, SourceBundle
from mlb_today.digest.results import build_results
from mlb_today.digest.standings import build_standings
from mlb_today.sources.fetched import Fetched

# The snapshot store's source names, as `sources/mlb.py` and `sources/fangraphs.py` write them.
SCHEDULE_TODAY = "mlb.schedule.today"
SCHEDULE_YESTERDAY = "mlb.schedule.yesterday"
STANDINGS = "mlb.standings"
BATTING = "fangraphs.batting"
PITCHING = "fangraphs.pitching"


def build_digest(day: date, bundle: SourceBundle) -> Digest:
    """A full digest when today's schedule has a game, else a scores-only one.

    A source that fell back to its snapshot is in `stale` with the snapshot's time; a source with
    no snapshot either (`None` in the bundle) is in `unavailable` and its section is empty or
    `None`. An unavailable today's schedule shows no games, so it builds a scores-only digest.
    """
    # Only `fetched_at` and `stale` are read here, so the payload type does not matter.
    sources: dict[str, Fetched[Any] | None] = {
        SCHEDULE_TODAY: bundle.matchups,
        SCHEDULE_YESTERDAY: bundle.results,
        STANDINGS: bundle.standings,
        BATTING: bundle.batting,
        PITCHING: bundle.pitching,
    }
    sources.update({f"mlb.boxscore.{pk}": hrs for pk, hrs in bundle.home_runs.items()})
    stale: dict[str, datetime] = {
        name: fetched.fetched_at
        for name, fetched in sources.items()
        if fetched is not None and fetched.stale
    }
    unavailable = [name for name, fetched in sources.items() if fetched is None]

    pitching = None if bundle.pitching is None else bundle.pitching.data
    today = bundle.matchups
    full = today is not None and len(today.data.games) > 0
    return Digest(
        date=day,
        kind="full" if full else "scores_only",
        stale=stale,
        unavailable=unavailable,
        matchups=build_matchups(today.data, pitching) if today is not None and full else [],
        results=(
            []
            if bundle.results is None
            else build_results(
                bundle.results.data,
                {pk: hrs.data for pk, hrs in bundle.home_runs.items()},
                pitching,
            )
        ),
        standings=[] if bundle.standings is None else build_standings(bundle.standings.data),
        batting=(
            None
            if bundle.batting is None
            else build_batting(bundle.batting.data, bundle.batting.fetched_at)
        ),
        pitching=(
            None
            if bundle.pitching is None
            else build_pitching(bundle.pitching.data, bundle.pitching.fetched_at)
        ),
    )
