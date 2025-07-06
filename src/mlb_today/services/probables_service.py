""" Service for creating today's probables data """
from datetime import datetime
import json
import logging
from typing import Any

from src.mlb_today.services.storage_service import StorageService


# noinspection PyMethodMayBeStatic
class ProbablesService:
    """ Service for creating today's probables data """

    def __init__(self):
        # Instantiate the storage service once to reuse the client
        self.storage_service = StorageService()

    def _load_stats_from_blob(self, filename: str) -> list[dict[str, Any]]:
        """Helper method to load and parse stats data from a blob."""
        try:
            blob_bytes = self.storage_service.get_blob(filename).download_blob().readall()
            # Safely get the 'data' key, defaulting to an empty list
            return json.loads(blob_bytes).get("data", [])
        except json.JSONDecodeError as err:
            logging.error(f"JSON decode error for {filename}: {err}", exc_info=True)
        except Exception as err:
            logging.error(f"Failed to load or parse {filename}: {err}", exc_info=True)
        return []

    def get_probables_data(self, probables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Get data for today's teams and probable pitchers."""
        pitching = self._load_stats_from_blob('pitching.json')
        if not pitching:
            logging.warning("Could not load pitching stats. Pitcher data will be incomplete.")

        games: list[dict[str, Any]] = []
        for game in probables:
            away_team: dict[str, Any] = game.get("teams", {}).get("away", {})
            home_team: dict[str, Any] = game.get("teams", {}).get("home", {})
            away_pitcher: dict[str, Any] = away_team.get("probablePitcher", {})
            home_pitcher: dict[str, Any] = home_team.get("probablePitcher", {})
            venue: dict[str, Any] = game.get("venue", {})
            location: dict[str, Any] = venue.get("location", {})
            broadcasts: list[dict[str, Any]] = game.get("broadcasts", [])

            # Use an f-string for cleaner formatting
            venue_str = f"{venue.get('name', 'N/A')}, ({location.get('city', '?')}, {location.get('stateAbbrev', '?')})"

            matchup = {
                "date": game.get("gameDate"),
                "venue": venue_str,
                "away": self.get_matchup_team(away_team, away_pitcher, pitching),
                "home": self.get_matchup_team(home_team, home_pitcher, pitching),
                "watch": self.get_tv_watch(broadcasts)
            }
            games.append(matchup)
        return games

    def get_matchup_team(self, team: dict, pitcher: dict, pitching_stats: list) -> dict:
        """Get team data for matchup."""
        pitcher_id = pitcher.get("id")

        def get_stat_as_float(stat_key: str, default_value: float = 0.0) -> float:
            """Safely retrieves a stat and converts it to a float."""
            stat_value = self.get_pitcher_stat(stat_key, pitcher_id, pitching_stats)
            if stat_value is None:
                return default_value
            try:
                # Ensure the stat is always a number for the template
                return float(stat_value)
            except (ValueError, TypeError):
                return default_value

        return {
            "abbr": team.get("team", {}).get("abbreviation"),
            "record": {
                "wins": team.get("leagueRecord", {}).get("wins", 'N/A'),
                "losses": team.get("leagueRecord", {}).get("losses", 'N/A')
            },
            "pitcher": {
                "name": pitcher.get("fullName"),
                "record": {
                    "wins": get_stat_as_float('W'),
                    "losses": get_stat_as_float('L')
                },
                "era": get_stat_as_float('ERA'),
                "xfip": get_stat_as_float('xFIP'),
                "war": get_stat_as_float('WAR')
            },
        }

    def get_pitcher_stat(self, stat_key: str, pitcher_id: int, pitching_stats: list) -> str | None:
        """Finds a stat for a pitcher, safely comparing IDs."""
        if not pitcher_id:
            return None

        # Use a generator expression with next() for efficiency
        try:
            pitcher_data = next(
                (p for p in pitching_stats if int(p.get('xMLBAMID', 0)) == pitcher_id),
                None
            )
            return pitcher_data.get(stat_key) if pitcher_data else None
        except (ValueError, TypeError):
            # This handles cases where xMLBAMID is not a valid integer
            logging.warning(f"Encountered a non-integer pitcher ID in stats data.")
            return None

    def get_off_war_leaders(self) -> list[dict[str, Any]]:
        """Get today's top 25 offensive WAR leaders."""
        batting = self._load_stats_from_blob('batting.json')
        off_war_leaders: list[dict[str, Any]] = []

        for batter in batting[:25]:
            leader = {
                "name": batter.get("PlayerName"),
                "team": batter.get("TeamNameAbb"),
                "avg": batter.get("AVG"),
                "hr": batter.get("HR"),
                "obp": batter.get("OBP"),
                "slg": batter.get("SLG"),
                "ops": batter.get("OPS"),
                "babip": batter.get("BABIP"),
                "war": batter.get("WAR")
            }
            off_war_leaders.append(leader)
        return off_war_leaders

    def get_pitching_war_leaders(self) -> list[dict[str, Any]]:
        """Get today's top 25 pitching WAR leaders."""
        pitching = self._load_stats_from_blob('pitching.json')
        pitching_war_leaders: list[dict[str, Any]] = []

        for pitcher in pitching[:25]:
            leader = {
                "name": pitcher.get("PlayerName"),
                "team": pitcher.get("TeamNameAbb"),
                "w": pitcher.get("W"),
                "l": pitcher.get("L"),
                "era": pitcher.get("ERA"),
                "xfip": pitcher.get("xFIP"),
                "war": pitcher.get("WAR")
            }
            pitching_war_leaders.append(leader)
        return pitching_war_leaders

    def get_tv_watch(self, broadcasts: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Get TV broadcasts for a game.

        Args:
            broadcasts (dict): list of all broadcast data.

        Returns:
            dict: dictionary of broadcasts.
        """
        if not broadcasts:
            return None

        home = []
        away = []
        national = []
        misc = []

        for broadcast in broadcasts:
            if broadcast.get("type") == "TV":
                if broadcast.get("isNational") and broadcast.get("callSign") not in national:
                    national.append(broadcast.get("callSign"))
                else:
                    if broadcast.get("homeAway") == "home" and broadcast.get("callSign") not in national:
                        home.append(broadcast.get("callSign"))
                    elif broadcast.get("homeAway") == "away" and broadcast.get("callSign") not in national:
                        away.append(broadcast.get("callSign"))
                    else:
                        if broadcast.get("callSign") not in national:
                            misc.append(broadcast.get("callSign"))

        tvwatch = {
            "home": home,
            "away": away,
            "national": national,
            "misc": misc
        }

        return tvwatch