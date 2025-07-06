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
            away_team = game.get("teams", {}).get("away", {})
            home_team = game.get("teams", {}).get("home", {})
            away_pitcher = away_team.get("probablePitcher", {})
            home_pitcher = home_team.get("probablePitcher", {})
            venue = game.get("venue", {})
            location = venue.get("location", {})

            # Use an f-string for cleaner formatting
            venue_str = f"{venue.get('name', 'N/A')}, ({location.get('city', '?')}, {location.get('stateAbbrev', '?')})"

            matchup = {
                "date": self.format_iso_to_ampm(game.get("gameDate")),
                "venue": venue_str,
                "away": self.get_matchup_team(away_team, away_pitcher, pitching),
                "home": self.get_matchup_team(home_team, home_pitcher, pitching)
            }
            games.append(matchup)
        return games

    def get_matchup_team(self, team: dict, pitcher: dict, pitching_stats: list) -> dict:
        """Get team data for matchup."""
        pitcher_id = pitcher.get("id")

        pitcher_wins = self.get_pitcher_stat('W', pitcher_id, pitching_stats)
        pitcher_losses = self.get_pitcher_stat('L', pitcher_id, pitching_stats)
        pitcher_era = self.get_pitcher_stat('ERA', pitcher_id, pitching_stats)
        pitcher_xfip = self.get_pitcher_stat('xFIP', pitcher_id, pitching_stats)
        pitcher_war = self.get_pitcher_stat('WAR', pitcher_id, pitching_stats)

        if not pitcher_wins:
            pitcher_wins = 0.0
        if not pitcher_losses:
            pitcher_losses = 0.0
        if not pitcher_era:
            pitcher_era = 0.0
        if not pitcher_xfip:
            pitcher_xfip = 0.0
        if not pitcher_war:
            pitcher_war = 0.0

        return {
            "abbr": team.get("team", {}).get("abbreviation"),
            "record": {
                "wins": team.get("leagueRecord", {}).get("wins", 'N/A'),
                "losses": team.get("leagueRecord", {}).get("losses", 'N/A')
            },
            "pitcher": {
                "name": pitcher.get("fullName"),
                "record": {
                    "wins": pitcher_wins,
                    "losses": pitcher_losses
                },
                "era": pitcher_era,
                "xfip": pitcher_xfip,
                "war": pitcher_war
            }
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

    def format_iso_to_ampm(self, iso_string: str) -> str:
        """
        Converts an ISO 8601 datetime string (e.g., '2025-06-27T18:40:00-04:00')
        into a human-readable 12-hour format (e.g., '6:40 PM').
        """
        if not iso_string:
            return "N/A"
        try:
            # 1. Parse the string into a timezone-aware datetime object.
            #    fromisoformat() handles the timezone offset automatically.
            dt_object = datetime.fromisoformat(iso_string)

            # 2. Format the object into a 12-hour string with AM/PM.
            #    - %I: Hour (12-hour clock) as a zero-padded decimal number.
            #    - %M: Minute as a zero-padded decimal number.
            #    - %p: Locale’s equivalent of either AM or PM.
            formatted_time = dt_object.strftime("%I:%M %p")

            # 3. Remove the leading zero from the hour (e.g., '06:40 PM' -> '6:40 PM')
            if formatted_time.startswith('0'):
                return formatted_time[1:]
            return formatted_time
        except (ValueError, TypeError):
            # Return a fallback value if the input string is malformed
            return "Invalid Time"
