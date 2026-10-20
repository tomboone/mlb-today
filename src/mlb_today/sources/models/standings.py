"""The MLB Stats API standings response: the fields spec §5.1 reads, everything else ignored."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, frozen=True)


class League(_Model):
    # `hydrate=division` names the division but leaves the league as an id and link.
    id: int


class Division(_Model):
    id: int
    name: str
    name_short: str


class Team(_Model):
    id: int
    abbreviation: str


class Streak(_Model):
    streak_code: str


class SplitRecord(_Model):
    type: str
    wins: int
    losses: int


class Records(_Model):
    split_records: list[SplitRecord] = []


class TeamRecord(_Model):
    team: Team
    wins: int
    losses: int
    # Strings as sent: ".605", and "-" for the division leader.
    winning_percentage: str
    games_back: str
    # Absent before a team's first game of the season.
    streak: Streak | None = None
    records: Records = Records()

    @property
    def last_ten(self) -> SplitRecord | None:
        return next((r for r in self.records.split_records if r.type == "lastTen"), None)


class DivisionRecord(_Model):
    league: League
    division: Division
    team_records: list[TeamRecord]


class StandingsResponse(_Model):
    records: list[DivisionRecord] = []
