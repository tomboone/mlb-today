"""The MLB Stats API schedule response: the fields spec §5.1 reads, everything else ignored."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, frozen=True)


class Person(_Model):
    id: int
    full_name: str


class Team(_Model):
    id: int
    name: str
    abbreviation: str


class LeagueRecord(_Model):
    wins: int
    losses: int


class GameTeam(_Model):
    team: Team
    league_record: LeagueRecord
    probable_pitcher: Person | None = None


class GameTeams(_Model):
    away: GameTeam
    home: GameTeam


class Location(_Model):
    city: str | None = None
    state_abbrev: str | None = None


class Venue(_Model):
    id: int
    name: str
    location: Location | None = None


class Broadcast(_Model):
    type: str
    name: str
    call_sign: str | None = None
    is_national: bool = False
    home_away: str | None = None


class Status(_Model):
    detailed_state: str


class LinescoreTotals(_Model):
    runs: int | None = None
    hits: int | None = None
    errors: int | None = None


class Inning(_Model):
    num: int
    away: LinescoreTotals
    home: LinescoreTotals


class LinescoreTeams(_Model):
    away: LinescoreTotals
    home: LinescoreTotals


class Linescore(_Model):
    current_inning: int | None = None
    innings: list[Inning] = []
    teams: LinescoreTeams | None = None


class Decisions(_Model):
    winner: Person | None = None
    loser: Person | None = None
    save: Person | None = None


class Game(_Model):
    game_pk: int
    game_date: datetime
    status: Status
    teams: GameTeams
    venue: Venue
    broadcasts: list[Broadcast] = []
    linescore: Linescore | None = None
    decisions: Decisions | None = None


class ScheduleDate(_Model):
    games: list[Game] = []


class ScheduleResponse(_Model):
    dates: list[ScheduleDate] = []

    @property
    def games(self) -> list[Game]:
        """Every game across `dates`; empty on a no-game day, when `dates` is `[]`."""
        return [game for day in self.dates for game in day.games]
