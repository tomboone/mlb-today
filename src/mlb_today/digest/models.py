"""The digest: everything the email shows (spec §6), plus the raw inputs it is built from."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mlb_today.sources.fetched import Fetched
from mlb_today.sources.models.boxscore import HomeRunRaw
from mlb_today.sources.models.fangraphs import BatterRaw, PitcherRaw
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.sources.models.standings import StandingsResponse


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class PitcherLine(_Model):
    # Fangraphs fields that did not coerce stay `None`; the line never invents zeros.
    w: int | None
    l: int | None  # noqa: E741 -- spec §6 names it, beside `w`
    era: float | None
    xfip: float | None
    war: float | None


class Probable(_Model):
    name: str
    # `None` when the pitcher is TBD, has no Fangraphs row, or Fangraphs is unavailable.
    line: PitcherLine | None


class Side(_Model):
    abbr: str
    wins: int
    losses: int
    probable: Probable


class Broadcasts(_Model):
    national: list[str] = []
    home: list[str] = []
    away: list[str] = []
    misc: list[str] = []


class Matchup(_Model):
    first_pitch: datetime
    status: str
    away: Side
    home: Side
    venue: str
    tv: Broadcasts


class HomeRun(_Model):
    player: str
    season_total: int


class ResultSide(_Model):
    abbr: str
    # `None` for a game with no linescore yet (postponed, not started).
    runs: int | None
    hits: int | None
    errors: int | None
    home_runs: list[HomeRun] = []


class Decision(_Model):
    name: str
    wins: int | None = None
    losses: int | None = None
    # Set on the save decision only.
    saves: int | None = None


class Decisions(_Model):
    winner: Decision
    loser: Decision
    save: Decision | None = None


class Result(_Model):
    status: str
    # `None` for a nine-inning game.
    innings: int | None
    away: ResultSide
    home: ResultSide
    decisions: Decisions | None = None
    stale_note: str | None = None


class StandingsRow(_Model):
    abbr: str
    w: int
    l: int  # noqa: E741 -- spec §6 names it, beside `w`
    pct: str
    gb: str  # "-" for the division leader
    last_ten: str
    streak: str


class DivisionStandings(_Model):
    league: str
    division: str
    rows: list[StandingsRow]


class LeaderRow(_Model):
    player: str
    team: str
    war: float | None
    # Batting columns.
    avg: float | None = None
    hr: int | None = None
    ops: float | None = None
    # Pitching columns.
    wins: int | None = None
    losses: int | None = None
    era: float | None = None
    xfip: float | None = None


class Leaderboard(_Model):
    kind: Literal["batting", "pitching"]
    rows: list[LeaderRow]
    as_of: datetime


class Digest(_Model):
    date: date
    kind: Literal["full", "scores_only"]
    # Source name → snapshot time, for each source that fell back to its snapshot.
    stale: dict[str, datetime] = {}
    matchups: list[Matchup] = []
    results: list[Result] = []
    standings: list[DivisionStandings] = []
    # `None` when the source and its snapshot were both unavailable; the section is omitted.
    batting: Leaderboard | None = None
    pitching: Leaderboard | None = None


@dataclass(frozen=True, slots=True)
class SourceBundle:
    """Every fetched source a digest is built from; `None` where a source had no snapshot either.

    A dataclass rather than a pydantic model: it carries already-parsed `Fetched` values from
    `sources/`, which must not be validated a second time.
    """

    matchups: Fetched[ScheduleResponse] | None = None
    results: Fetched[ScheduleResponse] | None = None
    # Keyed by game pk; only final games have an entry.
    home_runs: dict[int, Fetched[list[HomeRunRaw]]] = field(
        default_factory=dict[int, Fetched[list[HomeRunRaw]]]
    )
    standings: Fetched[StandingsResponse] | None = None
    batting: Fetched[list[BatterRaw]] | None = None
    pitching: Fetched[list[PitcherRaw]] | None = None
