"""The digest → the email: subject, MJML-compiled HTML, and a plain-text alternative (spec §6).

Pure: Jinja2 renders the MJML and text templates from the `Digest`, and `mjml` (the Python port
of the compiler, ADR-0003) turns the MJML into mail-client HTML. No I/O beyond the packaged
templates.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import mjml
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from mlb_today.digest.build import BATTING, PITCHING, SCHEDULE_TODAY, SCHEDULE_YESTERDAY, STANDINGS
from mlb_today.digest.models import Digest, Result

# Every time in the digest reads in Eastern, like the game day it belongs to.
EASTERN = ZoneInfo("America/New_York")
DASH = "—"
# A matchup in one of these states is on schedule, so the email does not call out its status.
SCHEDULED_STATUSES = frozenset({"Scheduled", "Pre-Game", "Warmup"})
SOURCE_LABELS = {
    SCHEDULE_TODAY: "MLB schedule",
    SCHEDULE_YESTERDAY: "MLB scores",
    STANDINGS: "MLB standings",
    BATTING: "Fangraphs batting",
    PITCHING: "Fangraphs pitching",
}
# One snapshot per final game; the banner collapses them into one line.
BOXSCORE_PREFIX = "mlb.boxscore."
BOXSCORE_LABEL = "MLB box scores"


@dataclass(frozen=True, slots=True)
class Rendered:
    subject: str
    html: str
    text: str


def render(digest: Digest) -> Rendered:
    """The digest's subject, HTML, and text alternative.

    Raises `ValueError` when the MJML does not compile.
    """
    title = subject(digest)
    context = {
        "digest": digest,
        "subject": title,
        "stale": _stale(digest),
        "unavailable": list(dict.fromkeys(_label(name) for name in digest.unavailable)),
        "scheduled_statuses": SCHEDULED_STATUSES,
    }
    source = _ENV.get_template("digest.mjml.j2").render(context)
    return Rendered(
        subject=title,
        html=mjml.mjml2html(source, disable_comments=True),
        text=_ENV.get_template("digest.txt.j2").render(context),
    )


def subject(digest: Digest) -> str:
    title = "MLB Today" if digest.kind == "full" else "MLB Scores"
    return f"{title} — {digest.date:%b} {digest.date.day}"


def ampm(when: datetime) -> str:
    """`1:05 PM`, in Eastern."""
    local = when.astimezone(EASTERN)
    return f"{local:%I:%M %p}".removeprefix("0")


def pct(value: float | None) -> str:
    """A rate stat the way box scores print it: `.279`, `1.042`."""
    if value is None:
        return DASH
    text = f"{value:.3f}"
    return text.removeprefix("0") if value >= 0 else text


def era(value: float | None) -> str:
    return DASH if value is None else f"{value:.2f}"


def war(value: float | None) -> str:
    return DASH if value is None else f"{value:.1f}"


def dash[T](value: T | None) -> T | str:
    return DASH if value is None else value


def stamp(when: datetime) -> str:
    """`Sep 27, 9:00 AM ET`."""
    local = when.astimezone(EASTERN)
    return f"{local:%b} {local.day}, {ampm(local)} ET"


def long_date(day: date) -> str:
    return f"{day:%A, %B} {day.day}, {day.year}"


def score_note(result: Result) -> str:
    """What follows a final score: `F/10` for extra (or fewer) innings, plus any status beyond
    a plain `Final` (`Completed Early: Rain`). Empty for a nine-inning `Final`."""
    parts = [result.status] if result.status != "Final" else []
    if result.innings is not None:
        parts.append(f"F/{result.innings}")
    return ", ".join(parts)


def _label(name: str) -> str:
    return BOXSCORE_LABEL if name.startswith(BOXSCORE_PREFIX) else SOURCE_LABELS.get(name, name)


def _stale(digest: Digest) -> list[tuple[str, datetime]]:
    """Each stale source's label and snapshot time; collapsed labels keep their oldest time."""
    oldest: dict[str, datetime] = {}
    for name, when in digest.stale.items():
        label = _label(name)
        oldest[label] = min(when, oldest.get(label, when))
    return list(oldest.items())


_ENV = Environment(
    loader=PackageLoader("mlb_today.render", "templates"),
    autoescape=select_autoescape(enabled_extensions=("mjml.j2",), default_for_string=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_FILTERS: dict[str, Callable[..., object]] = {
    "ampm": ampm,
    "pct": pct,
    "era": era,
    "war": war,
    "dash": dash,
    "stamp": stamp,
    "long_date": long_date,
    "score_note": score_note,
}
_ENV.filters.update(_FILTERS)
