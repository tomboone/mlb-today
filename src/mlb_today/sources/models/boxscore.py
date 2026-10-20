"""The MLB Stats API boxscore response: per-player home runs (spec §5.1), the rest ignored."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

type Side = Literal["away", "home"]


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, frozen=True)


class Person(_Model):
    id: int
    full_name: str


class Batting(_Model):
    # A player who did not bat (most pitchers) has `"batting": {}`.
    home_runs: int = 0


class PlayerStats(_Model):
    batting: Batting = Batting()


class Player(_Model):
    person: Person
    stats: PlayerStats
    season_stats: PlayerStats


class BoxscoreTeam(_Model):
    # Keyed `ID<mlbam id>`.
    players: dict[str, Player] = {}


class BoxscoreTeams(_Model):
    away: BoxscoreTeam
    home: BoxscoreTeam


@dataclass(frozen=True, slots=True)
class HomeRunRaw:
    side: Side
    player_id: int
    name: str
    home_runs: int
    season_total: int


class BoxscoreResponse(_Model):
    teams: BoxscoreTeams

    def home_runs(self) -> list[HomeRunRaw]:
        """Every player who homered in this game, away side first, in boxscore order."""
        sides: tuple[tuple[Side, BoxscoreTeam], ...] = (
            ("away", self.teams.away),
            ("home", self.teams.home),
        )
        return [
            HomeRunRaw(
                side=side,
                player_id=player.person.id,
                name=player.person.full_name,
                home_runs=player.stats.batting.home_runs,
                season_total=player.season_stats.batting.home_runs,
            )
            for side, team in sides
            for player in team.players.values()
            if player.stats.batting.home_runs > 0
        ]
