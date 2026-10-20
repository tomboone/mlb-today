"""MLB Stats API client (spec §5.1)."""

from datetime import date
from typing import Literal

import httpx

from mlb_today.sources.fetched import Fetched, fetch_or_snapshot
from mlb_today.sources.models.schedule import ScheduleResponse
from mlb_today.sources.snapshot import Payload, SnapshotStore

type Hydrate = Literal["matchups", "results"]

SCHEDULE_PATH = "/api/v1/schedule"
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


class MlbClient:
    def __init__(self, client: httpx.Client, store: SnapshotStore) -> None:
        self._client = client
        self._store = store

    def schedule(self, day: date, *, hydrate: Hydrate) -> Fetched[ScheduleResponse]:
        """The schedule for one Eastern date, hydrated for matchups or for results."""
        params = {
            "sportId": 1,
            "startDate": day.isoformat(),
            "endDate": day.isoformat(),
            "timeZone": TIME_ZONE,
            "sortBy": "gameDate,gameType",
            "hydrate": HYDRATE[hydrate],
        }

        def fetch() -> Payload:
            response = self._client.get(SCHEDULE_PATH, params=params)
            response.raise_for_status()
            return response.json()

        return fetch_or_snapshot(
            SOURCE[hydrate], fetch, ScheduleResponse.model_validate, self._store
        )
