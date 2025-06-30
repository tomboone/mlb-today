""" MLB.com API service """
import logging
from typing import Any

import requests

import src.mlb_today.config as config

SCHEDULE_ENDPOINT = config.SCHEDULE_ENDPOINT


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
        payload: dict[str, Any] = {
            "sportId": 1,
            "startDate": date,
            "endDate": date,
            "timeZone": "America/New_York",
            "sortBy": "gameDate,gameType",
            "hydrate": "team,broadcasts(all),venue(location),probablePitcher"
        }

        try:
            r: requests.Response = requests.get(self.endpoint, params=payload)
            r.raise_for_status()
        except requests.exceptions.HTTPError or requests.exceptions.RequestException as err:
            logging.error(err)
            return None

        return r.json()["dates"][0]["games"]
