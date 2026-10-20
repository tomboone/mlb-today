"""MLB Stats API client (spec §5.1)."""

from collections.abc import Callable
from datetime import date
from typing import Literal

import httpx

from mlb_today.sources.fetched import Fetched, fetch_or_snapshot
from mlb_today.sources.models.boxscore import BoxscoreResponse, HomeRunRaw
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.sources.models.standings import StandingsResponse
from mlb_today.sources.snapshot import Payload, SnapshotStore

type Hydrate = Literal["matchups", "results"]

SCHEDULE_PATH = "/api/v1/schedule"
STANDINGS_PATH = "/api/v1/standings"
TIME_ZONE = "America/New_York"

HYDRATE: dict[Hydrate, str] = {
    "matchups": "team,broadcasts(all),venue(location),probablePitcher",
    "results": "team,linescore,decisions",
}

# Matchups are always today's schedule and results always yesterday's (spec §4.2).
SOURCE: dict[Hydrate, str] = {
    "matchups": "mlb.schedule.today",
    "results": "mlb.schedule.yesterday",
}

# The American (103) and National (104) Leagues.
LEAGUE_IDS = "103,104"


class MlbClient:
    """Each source fetched through `client`, or, with no client, read from its snapshot alone."""

    def __init__(self, client: httpx.Client | None, store: SnapshotStore) -> None:
        self._client = client
        self._store = store

    def _getter(
        self, path: str, params: dict[str, str | int] | None = None
    ) -> Callable[[], Payload] | None:
        client = self._client
        if client is None:
            return None

        def fetch() -> Payload:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()

        return fetch

    def schedule(self, day: date, *, hydrate: Hydrate) -> Fetched[ScheduleResponse]:
        """The schedule for one Eastern date, hydrated for matchups or for results."""
        params: dict[str, str | int] = {
            "sportId": 1,
            "startDate": day.isoformat(),
            "endDate": day.isoformat(),
            "timeZone": TIME_ZONE,
            "sortBy": "gameDate,gameType",
            "hydrate": HYDRATE[hydrate],
        }
        return fetch_or_snapshot(
            SOURCE[hydrate],
            self._getter(SCHEDULE_PATH, params),
            ScheduleResponse.model_validate,
            self._store,
        )

    def boxscore_home_runs(self, game_pk: int) -> Fetched[list[HomeRunRaw]]:
        """The players who homered in one game, each with their season total after it."""
        return fetch_or_snapshot(
            f"mlb.boxscore.{game_pk}",
            self._getter(f"/api/v1/game/{game_pk}/boxscore"),
            lambda payload: BoxscoreResponse.model_validate(payload).home_runs(),
            self._store,
        )

    def standings(self, season: int) -> Fetched[StandingsResponse]:
        """Regular-season standings for both leagues, one record per division."""
        params: dict[str, str | int] = {
            "leagueId": LEAGUE_IDS,
            "season": season,
            "standingsTypes": "regularSeason",
            "hydrate": "team,division",
        }
        return fetch_or_snapshot(
            "mlb.standings",
            self._getter(STANDINGS_PATH, params),
            StandingsResponse.model_validate,
            self._store,
        )
