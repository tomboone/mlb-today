"""Today's schedule and the pitching leaderboard → matchups (spec §5.1, §6)."""

from mlb_today.digest.models import Broadcasts, Matchup, PitcherLine, Probable, Side
from mlb_today.sources.models.fangraphs import PitcherRaw
from mlb_today.sources.models.schedule import Broadcast, Game, GameTeam, ScheduleResponse, Venue

TBD = "TBD"


def build_matchups(schedule: ScheduleResponse, pitching: list[PitcherRaw] | None) -> list[Matchup]:
    """One matchup per game, ordered by first pitch, then game pk (doubleheaders keep both).

    `pitching` is `None` when Fangraphs and its snapshot were both unavailable: every probable
    then has `line=None`, as does any probable with no Fangraphs row.
    """
    lines = _pitcher_lines(pitching or [])
    games = sorted(schedule.games, key=lambda game: (game.game_date, game.game_pk))
    return [_matchup(game, lines) for game in games]


def _pitcher_lines(pitching: list[PitcherRaw]) -> dict[int, PitcherLine]:
    lines: dict[int, PitcherLine] = {}
    for row in pitching:
        if row.mlbam_id is not None and row.mlbam_id not in lines:
            lines[row.mlbam_id] = PitcherLine(
                w=row.wins, l=row.losses, era=row.era, xfip=row.xfip, war=row.war
            )
    return lines


def _matchup(game: Game, lines: dict[int, PitcherLine]) -> Matchup:
    return Matchup(
        first_pitch=game.game_date,
        status=game.status.detailed_state,
        away=_side(game.teams.away, lines),
        home=_side(game.teams.home, lines),
        venue=_venue(game.venue),
        tv=_broadcasts(game.broadcasts),
    )


def _side(team: GameTeam, lines: dict[int, PitcherLine]) -> Side:
    pitcher = team.probable_pitcher
    probable = (
        Probable(name=TBD, line=None)
        if pitcher is None
        else Probable(name=pitcher.full_name, line=lines.get(pitcher.id))
    )
    return Side(
        abbr=team.team.abbreviation,
        wins=team.league_record.wins,
        losses=team.league_record.losses,
        probable=probable,
    )


def _venue(venue: Venue) -> str:
    """`"{name}, {city}, {state}"`, dropping whichever location parts MLB left out."""
    location = venue.location
    parts = [venue.name]
    if location is not None:
        parts += [part for part in (location.city, location.state_abbrev) if part]
    return ", ".join(parts)


def _broadcasts(broadcasts: list[Broadcast]) -> Broadcasts:
    """TV only. National wins over home/away; misc is a TV feed with neither (spec §2 bug fix)."""
    national: list[str] = []
    home: list[str] = []
    away: list[str] = []
    misc: list[str] = []
    tv = [b for b in broadcasts if b.type == "TV"]
    for b in tv:
        if b.is_national:
            _add(national, b)
    for b in tv:
        if b.is_national or _label(b) in national:
            continue
        match b.home_away:
            case "home":
                _add(home, b)
            case "away":
                _add(away, b)
            case _:
                _add(misc, b)
    return Broadcasts(national=national, home=home, away=away, misc=misc)


def _label(broadcast: Broadcast) -> str:
    return broadcast.call_sign or broadcast.name


def _add(labels: list[str], broadcast: Broadcast) -> None:
    label = _label(broadcast)
    if label not in labels:
        labels.append(label)
