"""The standings response → one table per division (spec §5.1, §6)."""

from mlb_today.digest.models import DivisionStandings, StandingsRow
from mlb_today.sources.models.standings import DivisionRecord, StandingsResponse, TeamRecord

# MLB division ids, in display order: AL East, AL Central, AL West, NL East, NL Central, NL West.
DIVISION_ORDER = (201, 202, 200, 204, 205, 203)
LEADER_GB = "-"
NO_RECORD = "-"


def build_standings(resp: StandingsResponse) -> list[DivisionStandings]:
    """One table per division, AL East … NL West; rows by games back, then most wins.

    A division the order does not know sorts last rather than being dropped.
    """
    records = sorted(resp.records, key=_division_rank)
    return [_division(record) for record in records]


def _division_rank(record: DivisionRecord) -> int:
    division_id = record.division.id
    if division_id not in DIVISION_ORDER:
        return len(DIVISION_ORDER)
    return DIVISION_ORDER.index(division_id)


def _division(record: DivisionRecord) -> DivisionStandings:
    # `name_short` is "AL East": the league, then the division.
    league, _, division = record.division.name_short.partition(" ")
    teams = sorted(record.team_records, key=lambda team: (_games_back(team), -team.wins))
    return DivisionStandings(league=league, division=division, rows=[_row(t) for t in teams])


def _games_back(team: TeamRecord) -> float:
    return 0.0 if team.games_back == LEADER_GB else float(team.games_back)


def _row(team: TeamRecord) -> StandingsRow:
    last_ten = team.last_ten
    return StandingsRow(
        abbr=team.team.abbreviation,
        w=team.wins,
        l=team.losses,
        pct=team.winning_percentage,
        gb=team.games_back,
        last_ten=NO_RECORD if last_ten is None else f"{last_ten.wins}-{last_ten.losses}",
        streak=NO_RECORD if team.streak is None else team.streak.streak_code,
    )
