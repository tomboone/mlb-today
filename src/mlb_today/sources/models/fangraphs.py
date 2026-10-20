"""The Fangraphs leaders response: the fields spec §5.2 reads, everything else ignored.

Fangraphs is unofficial: a numeric field may be missing, null, or a string, and none of those
may fail the table. Each one coerces what it can and is `None` otherwise.
"""

import math
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _to_int(value: object) -> int | None:
    # Counting stats arrive as floats (`45.0`); a fractional one is not a count.
    number = _to_float(value)
    return int(number) if number is not None and number.is_integer() else None


Rate = Annotated[float | None, BeforeValidator(_to_float)]
Count = Annotated[int | None, BeforeValidator(_to_int)]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class _Player(_Model):
    player_name: str = Field(alias="PlayerName")
    team: str = Field(alias="TeamNameAbb")
    # Not every player has an MLBAM id; one without can still be listed, just never matched.
    mlbam_id: Count = Field(default=None, alias="xMLBAMID")
    war: Rate = Field(default=None, alias="WAR")


class BatterRaw(_Player):
    avg: Rate = Field(default=None, alias="AVG")
    hr: Count = Field(default=None, alias="HR")
    obp: Rate = Field(default=None, alias="OBP")
    slg: Rate = Field(default=None, alias="SLG")
    ops: Rate = Field(default=None, alias="OPS")
    babip: Rate = Field(default=None, alias="BABIP")


class PitcherRaw(_Player):
    wins: Count = Field(default=None, alias="W")
    losses: Count = Field(default=None, alias="L")
    saves: Count = Field(default=None, alias="SV")
    era: Rate = Field(default=None, alias="ERA")
    xfip: Rate = Field(default=None, alias="xFIP")


class BattingResponse(_Model):
    data: list[BatterRaw] = []


class PitchingResponse(_Model):
    data: list[PitcherRaw] = []
