""" Fangraphs API service """
import logging
from typing import Any

import requests

import src.mlb_today.config as config

STATS_ENDPOINT = config.STATS_ENDPOINT

class FangraphsService:
    """ Fangraphs API service """
    def __init__(self):
        self.endpoint = STATS_ENDPOINT

    def get_data(
            self, position: str, stats_type: str, year: str, sort_dir: str = None, sort_stat: str = None
    ) -> dict[str, Any] | None:
        """
        Get data from Fangraphs API

        Args:
            position (str): position to get stats for
            stats_type (str): type of stats to get
            year (int): year to get stats for
            sort_dir (str): sort direction
            sort_stat (str): sort stat

        Returns:
            dict[str, Any]: data from Fangraphs API
        """
        payload: dict[str, Any] = {
            "pos": position,
            "stats": stats_type,
            "lg": "all",
            "qual": "y",
            "season": year,
            "pageItems": 2000000000,
            "sortDir": sort_dir,
            "sortStat": sort_stat
        }

        try:
            r: requests.Response = requests.get(self.endpoint, params=payload)
            r.raise_for_status()
        except requests.exceptions.HTTPError or requests.exceptions.RequestException as err:
            logging.error(err)
            return None

        return r.json()
