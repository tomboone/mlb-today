"""Fangraphs leaders client (spec §5.2)."""

from collections.abc import Callable
from typing import Literal

import httpx

from mlb_today.sources.fetched import Fetched, fetch_or_snapshot
from mlb_today.sources.models.fangraphs import (
    BatterRaw,
    BattingResponse,
    PitcherRaw,
    PitchingResponse,
)
from mlb_today.sources.snapshot import Payload, SnapshotStore

type Stats = Literal["bat", "pit"]

# The digest shows the top 25 batters.
BATTING_ROWS = 25
# Every pitcher: probables and decisions are matched by MLBAM id wherever they rank.
PITCHING_ROWS = 2000


class FangraphsClient:
    def __init__(self, client: httpx.Client, store: SnapshotStore) -> None:
        self._client = client
        self._store = store
        # The base URL is the whole endpoint. httpx gives it a trailing slash, which Fangraphs
        # answers with a 301, so request it absolutely without one.
        self._url = str(client.base_url).rstrip("/")

    def _getter(self, stats: Stats, season: int, page_items: int) -> Callable[[], Payload]:
        params: dict[str, str | int] = {
            "pos": "all",
            "stats": stats,
            "lg": "all",
            "qual": "n",
            "season": season,
            "sortDir": "default",
            "sortStat": "WAR",
            "pageItems": page_items,
        }

        def fetch() -> Payload:
            response = self._client.get(self._url, params=params)
            response.raise_for_status()
            return response.json()

        return fetch

    def batting(self, season: int) -> Fetched[list[BatterRaw]]:
        """The season's top batters by WAR."""
        return fetch_or_snapshot(
            "fangraphs.batting",
            self._getter("bat", season, BATTING_ROWS),
            lambda payload: BattingResponse.model_validate(payload).data,
            self._store,
        )

    def pitching(self, season: int) -> Fetched[list[PitcherRaw]]:
        """Every pitcher with a season line, by WAR."""
        return fetch_or_snapshot(
            "fangraphs.pitching",
            self._getter("pit", season, PITCHING_ROWS),
            lambda payload: PitchingResponse.model_validate(payload).data,
            self._store,
        )
