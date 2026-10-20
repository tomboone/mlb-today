from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from mlb_today.digest.build import build_digest
from mlb_today.digest.models import Broadcasts, Digest, Result, ResultSide
from mlb_today.render.render import ampm, dash, era, pct, render, score_note, stamp, war
from mlb_today.sources.fetched import Fetched
from tests.bundles import SNAPSHOT_AT, full_bundle, schedule

DAY = date(2026, 9, 28)


class HTMLSnapshot(SingleFileSnapshotExtension):
    """One browsable `.html` file per snapshot, so a reviewer can open the rendered email."""

    file_extension = "html"
    _write_mode = WriteMode.TEXT


class TextSnapshot(SingleFileSnapshotExtension):
    file_extension = "txt"
    _write_mode = WriteMode.TEXT


def _full() -> Digest:
    return build_digest(DAY, full_bundle())


def _scores_only() -> Digest:
    return build_digest(DAY, replace(full_bundle(), matchups=schedule("schedule_empty")))


def _stale() -> Digest:
    bundle = full_bundle()
    assert bundle.pitching is not None
    pitching = Fetched(bundle.pitching.data, SNAPSHOT_AT, stale=True)
    return build_digest(DAY, replace(bundle, pitching=pitching))


DIGESTS = {"full": _full, "scores_only": _scores_only, "stale": _stale}


@pytest.mark.parametrize("kind", DIGESTS)
def test_html_matches_the_snapshot(kind: str, snapshot: SnapshotAssertion) -> None:
    # `render` raises `ValueError` when `mjml` cannot compile the source, so a match also means a
    # clean compile. The compiler rejects malformed markup but tolerates unknown tags.
    assert render(DIGESTS[kind]()).html == snapshot.use_extension(HTMLSnapshot)


@pytest.mark.parametrize("kind", DIGESTS)
def test_text_matches_the_snapshot(kind: str, snapshot: SnapshotAssertion) -> None:
    assert render(DIGESTS[kind]()).text == snapshot.use_extension(TextSnapshot)


def test_full_html_is_under_the_size_budget() -> None:
    assert len(render(_full()).html.encode()) < 150_000


def test_subject_names_the_kind_and_date() -> None:
    assert render(_full()).subject == "MLB Today — Sep 28"
    assert render(_scores_only()).subject == "MLB Scores — Sep 28"


def test_scores_only_omits_matchups_but_keeps_results() -> None:
    rendered = render(_scores_only())

    assert "TODAY'S MATCHUPS" not in rendered.text
    assert "Comerica Park" not in rendered.html
    assert "YESTERDAY'S RESULTS" in rendered.text


def test_stale_source_shows_a_banner_naming_it_and_its_snapshot_time() -> None:
    rendered = render(_stale())
    banner = (
        "Fangraphs pitching could not be fetched; showing its snapshot from Sep 27, 9:00 AM ET."
    )

    assert banner in rendered.html
    assert banner in rendered.text


def test_fresh_digest_has_no_banner() -> None:
    assert "could not be fetched" not in render(_full()).html


def test_stale_box_scores_collapse_into_one_line_with_the_oldest_time() -> None:
    older = datetime(2026, 9, 27, 4, 0, tzinfo=UTC)
    digest = _full().model_copy(
        update={"stale": {"mlb.boxscore.1": SNAPSHOT_AT, "mlb.boxscore.2": older}}
    )

    text = render(digest).text

    assert text.count("MLB box scores could not be fetched") == 1
    assert "snapshot from Sep 27, 12:00 AM ET" in text


def test_unavailable_sources_are_named() -> None:
    digest = _full().model_copy(
        update={"unavailable": ["fangraphs.batting", "mlb.standings"], "batting": None}
    )

    rendered = render(digest)

    assert "Not available today: Fangraphs batting, MLB standings." in rendered.text
    assert "BATTING LEADERS" not in rendered.text


def test_broadcasts_list_national_home_away_then_misc() -> None:
    digest = _full()
    first = digest.matchups[0]
    tv = Broadcasts(national=["ESPN"], home=["DSN"], away=["NATS"], misc=["MLB.TV"])
    digest = digest.model_copy(update={"matchups": [first.model_copy(update={"tv": tv})]})

    rendered = render(digest)

    line = "TV: National: ESPN · DET: DSN · WSH: NATS · Other: MLB.TV"
    assert line in rendered.html
    assert line in rendered.text


def test_html_escapes_source_text() -> None:
    digest = _full()
    first = digest.matchups[0]
    renamed = first.model_copy(update={"venue": "Park & <Field>"})
    digest = digest.model_copy(update={"matchups": [renamed, *digest.matchups[1:]]})

    rendered = render(digest)

    assert "Park &amp; &lt;Field&gt;" in rendered.html
    assert "Park & <Field>" in rendered.text


def test_ampm_reads_in_eastern() -> None:
    assert ampm(datetime(2026, 9, 28, 17, 5, tzinfo=UTC)) == "1:05 PM"
    assert ampm(datetime(2026, 9, 29, 3, 40, tzinfo=UTC)) == "11:40 PM"


def test_stamp_reads_in_eastern() -> None:
    assert stamp(datetime(2026, 9, 27, 13, 0, tzinfo=UTC)) == "Sep 27, 9:00 AM ET"


@pytest.mark.parametrize(
    ("value", "expected"), [(0.2795, ".280"), (1.0427, "1.043"), (0.0, ".000"), (None, "—")]
)
def test_pct_drops_the_leading_zero(value: float | None, expected: str) -> None:
    assert pct(value) == expected


def test_era_war_and_dash_show_a_dash_for_none() -> None:
    assert (era(4.1143), era(None)) == ("4.11", "—")
    assert (war(-0.518), war(None)) == ("-0.5", "—")
    assert (dash(0), dash("TBD"), dash(None)) == (0, "TBD", "—")


@pytest.mark.parametrize(
    ("status", "innings", "expected"),
    [
        ("Final", None, ""),
        ("Final", 10, "F/10"),
        ("Completed Early: Rain", 6, "Completed Early: Rain, F/6"),
        ("Final: Tied", None, "Final: Tied"),
    ],
)
def test_score_note(status: str, innings: int | None, expected: str) -> None:
    side = ResultSide(abbr="NYY", runs=1, hits=1, errors=0)
    result = Result(status=status, innings=innings, away=side, home=side)

    assert score_note(result) == expected
