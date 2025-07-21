""" MLB.com API service """
from typing import Any

import requests

import src.mlb_today.config as config
from src.mlb_today.logger import logger


SCHEDULE_ENDPOINT: str = config.SCHEDULE_ENDPOINT


class MlbDotComService:
    """ MLB.com API service """
    def __init__(self):
        self.endpoint = SCHEDULE_ENDPOINT

    def get_schedule(self, date: str) -> list[dict[str, Any]] | None:
        """
        Get schedule for a given date

        Args:
            date (str): date in YYYY-MM-DD format

        Returns:
            list[dict[str, Any]]: list of games
        """
        payload: dict[str, Any] = {  # Create payload
            "sportId": 1,
            "startDate": date,
            "endDate": date,
            "timeZone": "America/New_York",
            "sortBy": "gameDate,gameType",
            "hydrate": "team,broadcasts(all),venue(location),probablePitcher"
        }

        try:
            r: requests.Response = requests.get(self.endpoint, params=payload)  # Get data
            r.raise_for_status()  # Raise error for HTTP status code
        except requests.exceptions.HTTPError or requests.exceptions.RequestException as err:
            logger.error(err)
            return None

        return r.json()["dates"][0].get("games", [])
