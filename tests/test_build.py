from dataclasses import replace
from datetime import date

import pytest

from mlb_today.digest.build import build_digest
from mlb_today.digest.models import SourceBundle
from mlb_today.sources.fetched import Fetched
from tests.bundles import BOXSCORE_PKS, FETCHED_AT, SNAPSHOT_AT, full_bundle, schedule

DAY = date(2026, 9, 28)
DIVISIONS = [
    ("AL", "East"),
    ("AL", "Central"),
    ("AL", "West"),
    ("NL", "East"),
    ("NL", "Central"),
    ("NL", "West"),
]


@pytest.fixture
def full() -> SourceBundle:
    return full_bundle()


def test_games_today_build_a_full_digest_with_every_section(full: SourceBundle) -> None:
    digest = build_digest(DAY, full)

    assert digest.date == DAY
    assert digest.kind == "full"
    assert digest.matchups
    assert digest.results
    assert [(d.league, d.division) for d in digest.standings] == DIVISIONS
    assert digest.batting is not None and digest.batting.as_of == FETCHED_AT
    assert digest.pitching is not None and len(digest.pitching.rows) == 25
    assert (digest.stale, digest.unavailable) == ({}, [])


def test_no_games_today_build_a_scores_only_digest(full: SourceBundle) -> None:
    bundle = replace(full, matchups=schedule("schedule_empty"))

    digest = build_digest(DAY, bundle)

    assert digest.kind == "scores_only"
    assert digest.matchups == []
    assert digest.results


def test_stale_sources_are_keyed_by_source_name_with_their_snapshot_time(
    full: SourceBundle,
) -> None:
    assert full.standings is not None
    pk = BOXSCORE_PKS[0]
    stale_hrs = Fetched(full.home_runs[pk].data, SNAPSHOT_AT, stale=True)
    bundle = replace(
        full,
        standings=Fetched(full.standings.data, SNAPSHOT_AT, stale=True),
        home_runs={**full.home_runs, pk: stale_hrs},
    )

    digest = build_digest(DAY, bundle)

    assert digest.stale == {"mlb.standings": SNAPSHOT_AT, f"mlb.boxscore.{pk}": SNAPSHOT_AT}
    assert len(digest.standings) == 6


def test_missing_standings_omit_the_section_and_say_so(full: SourceBundle) -> None:
    digest = build_digest(DAY, replace(full, standings=None))

    assert digest.standings == []
    assert digest.unavailable == ["mlb.standings"]


def test_missing_fangraphs_omit_the_leaderboards_but_keep_the_games(full: SourceBundle) -> None:
    digest = build_digest(DAY, replace(full, batting=None, pitching=None))

    assert (digest.batting, digest.pitching) == (None, None)
    assert digest.unavailable == ["fangraphs.batting", "fangraphs.pitching"]
    assert digest.matchups
    assert all(m.away.probable.line is None for m in digest.matchups)


def test_missing_schedules_build_a_scores_only_digest_without_games(full: SourceBundle) -> None:
    digest = build_digest(DAY, replace(full, matchups=None, results=None))

    assert digest.kind == "scores_only"
    assert (digest.matchups, digest.results) == ([], [])
    assert digest.unavailable == ["mlb.schedule.today", "mlb.schedule.yesterday"]


def test_no_games_yesterday_build_a_full_digest_without_results(full: SourceBundle) -> None:
    digest = build_digest(DAY, replace(full, results=schedule("schedule_empty"), home_runs={}))

    assert digest.kind == "full"
    assert digest.matchups
    assert digest.results == []
    assert digest.unavailable == []
