"""Fangraphs rows → the batting and pitching leaderboards (spec §5.2, §6)."""

from collections.abc import Sequence
from datetime import datetime

from mlb_today.digest.models import Leaderboard, LeaderRow
from mlb_today.sources.models.fangraphs import BatterRaw, PitcherRaw

LEADERS = 25


def build_batting(rows: Sequence[BatterRaw], as_of: datetime) -> Leaderboard:
    """The top 25 batters by WAR: name, team, AVG, HR, OPS, WAR."""
    return Leaderboard(
        kind="batting",
        rows=[
            LeaderRow(
                player=row.player_name,
                team=row.team,
                war=row.war,
                avg=row.avg,
                hr=row.hr,
                ops=row.ops,
            )
            for row in _top(rows)
        ],
        as_of=as_of,
    )


def build_pitching(rows: Sequence[PitcherRaw], as_of: datetime) -> Leaderboard:
    """The top 25 pitchers by WAR: name, team, W-L, ERA, xFIP, WAR."""
    return Leaderboard(
        kind="pitching",
        rows=[
            LeaderRow(
                player=row.player_name,
                team=row.team,
                war=row.war,
                wins=row.wins,
                losses=row.losses,
                era=row.era,
                xfip=row.xfip,
            )
            for row in _top(rows)
        ],
        as_of=as_of,
    )


def _top[T: BatterRaw | PitcherRaw](rows: Sequence[T]) -> list[T]:
    """The first 25 by WAR, highest first. A stat that did not coerce stays `None` in its row
    (rendered as a dash downstream); a row with no WAR sorts last rather than being dropped."""
    ranked = sorted(rows, key=lambda row: (row.war is None, -(row.war or 0.0)))
    return ranked[:LEADERS]
