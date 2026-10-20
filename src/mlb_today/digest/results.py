"""Yesterday's schedule, its box-score home runs and the pitching table → results (spec §6)."""

from mlb_today.digest.models import Decision, Decisions, HomeRun, Result, ResultSide
from mlb_today.sources.models.boxscore import HomeRunRaw, Side
from mlb_today.sources.models.fangraphs import PitcherRaw
from mlb_today.sources.models.schedule import (
    Decisions as RawDecisions,
)
from mlb_today.sources.models.schedule import (
    Game,
    GameTeam,
    LinescoreTotals,
    Person,
    ScheduleResponse,
)

FINAL = "Final"
REGULATION_INNINGS = 9


def build_results(
    schedule: ScheduleResponse,
    boxscores: dict[int, list[HomeRunRaw]],
    pitching: list[PitcherRaw] | None,
) -> list[Result]:
    """One result per game, ordered by first pitch, then game pk (doubleheaders keep both).

    Only a `Final` game carries a score, innings, decisions and home runs; any other status
    (postponed, suspended, …) carries the status and the teams alone. A final game with no
    `boxscores` entry has no home runs rather than failing. `pitching` is `None` when Fangraphs
    and its snapshot were both unavailable: every decision then has `None` records, as does any
    pitcher with no Fangraphs row.
    """
    records = _records(pitching or [])
    games = sorted(schedule.games, key=lambda game: (game.game_date, game.game_pk))
    return [_result(game, boxscores.get(game.game_pk, []), records) for game in games]


def _records(pitching: list[PitcherRaw]) -> dict[int, PitcherRaw]:
    records: dict[int, PitcherRaw] = {}
    for row in pitching:
        if row.mlbam_id is not None and row.mlbam_id not in records:
            records[row.mlbam_id] = row
    return records


def _result(game: Game, home_runs: list[HomeRunRaw], records: dict[int, PitcherRaw]) -> Result:
    status = game.status.detailed_state
    linescore = game.linescore
    if status != FINAL or linescore is None or linescore.teams is None:
        return Result(
            status=status,
            innings=None,
            away=_bare_side(game.teams.away),
            home=_bare_side(game.teams.home),
        )
    innings = linescore.current_inning or len(linescore.innings)
    return Result(
        status=status,
        innings=None if innings == REGULATION_INNINGS else innings,
        away=_side(game.teams.away, linescore.teams.away, "away", home_runs),
        home=_side(game.teams.home, linescore.teams.home, "home", home_runs),
        decisions=_decisions(game.decisions, records),
    )


def _bare_side(team: GameTeam) -> ResultSide:
    return ResultSide(abbr=team.team.abbreviation, runs=None, hits=None, errors=None)


def _side(
    team: GameTeam, totals: LinescoreTotals, side: Side, home_runs: list[HomeRunRaw]
) -> ResultSide:
    return ResultSide(
        abbr=team.team.abbreviation,
        runs=totals.runs,
        hits=totals.hits,
        errors=totals.errors,
        home_runs=[
            HomeRun(player=hr.name, season_total=hr.season_total)
            for hr in home_runs
            if hr.side == side
        ],
    )


def _decisions(decisions: RawDecisions | None, records: dict[int, PitcherRaw]) -> Decisions | None:
    # A final game without both a winner and a loser (a tie, a forfeit) has no decisions line.
    if decisions is None or decisions.winner is None or decisions.loser is None:
        return None
    save = decisions.save
    return Decisions(
        winner=_win_loss(decisions.winner, records),
        loser=_win_loss(decisions.loser, records),
        save=None if save is None else _save(save, records),
    )


def _win_loss(pitcher: Person, records: dict[int, PitcherRaw]) -> Decision:
    record = records.get(pitcher.id)
    if record is None:
        return Decision(name=pitcher.full_name)
    return Decision(name=pitcher.full_name, wins=record.wins, losses=record.losses)


def _save(pitcher: Person, records: dict[int, PitcherRaw]) -> Decision:
    record = records.get(pitcher.id)
    return Decision(name=pitcher.full_name, saves=None if record is None else record.saves)
