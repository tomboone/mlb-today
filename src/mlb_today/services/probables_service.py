import json
import logging
from typing import Any

from src.mlb_today.services.storage_service import StorageService


# noinspection PyMethodMayBeStatic
class ProbablesService:
    """ Service for creating today's probables data """
    def __init__(self):
        pass

    def get_probables_data(self, probables: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """
        Get data for today's teams and probable pitchers
        """
        try:
            storage_service: StorageService = StorageService()  # Create StorageService instance
            pitching_blob: bytes = storage_service.get_blob('pitching.json').download_blob().readall()  # Get blob
            pitching: list[dict[str, Any]] = json.loads(pitching_blob).get("data")  # Convert blob to list
        except Exception as err:  # If error, log and return
            logging.error(err)
            return None

        games: list[dict[str, Any]] = []  # List for games

        for game in probables:  # For each game
            away_team: dict[str, Any] = game.get("teams", {}).get("away", {})  # Get away team
            home_team: dict[str, Any] = game.get("teams", {}).get("home", {})  # Get home team

            away_pitcher: dict[str, Any] = away_team.get("probablePitcher", {})  # Get away pitcher
            home_pitcher: dict[str, Any] = home_team.get("probablePitcher", {})  # Get home pitcher

            stadium: str = game.get("venue", {}).get("name")  # Get stadium name
            location: dict[str, Any] = game.get("venue", {}).get("location")  # Get location
            city: str = location.get("city", "")  # Get city
            state: str = location.get("stateAbbrev", "")  # Get state

            matchup: dict[str, Any] = {  # Create matchup dict
                "date": game.get("gameDate"),
                "venue": stadium + ", (" + city + ", " + state + ")",
                "away": self.get_matchup_team(away_team, away_pitcher, pitching),
                "home": self.get_matchup_team(home_team, home_pitcher, pitching)
            }

            games.append(matchup)  # Add matchup dict to list

        return games

    def get_matchup_team(
            self, team: dict[str, Any], pitcher: dict[str, Any], pitching: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Get team data for matchup

        Args:
            team (dict): team dict
            pitcher (dict): pitcher dict
            pitching (list): pitching stats list

        Returns:
            dict: team data for matchup
        """
        matchup_team: dict[str, Any] = {  # Create matchup team dict
            "abbr": team.get("team", {}).get("abbreviation"),
            "record": {
                "wins": team.get("leagueRecord", {}).get("wins", 'N/A'),
                "losses": team.get("leagueRecord", {}).get("losses", 'N/A')
            },
            "pitcher": {
                "name": pitcher.get("fullName"),
                "record": {
                    "wins": self.get_pitcher_stat('W', pitcher.get("id"), pitching),
                    "losses": self.get_pitcher_stat('L', pitcher.get("id"), pitching)
                },
                "era": self.get_pitcher_stat('ERA', pitcher.get("id"), pitching),
                "xfip": self.get_pitcher_stat('xFIP', pitcher.get("id"), pitching),
                "war": self.get_pitcher_stat('WAR', pitcher.get("id"), pitching)
            }
        }

        return matchup_team

    def get_pitcher_stat(self, stat_key: str, pitcher_id: int, pitching_stats: list[dict[str, Any]]) -> str | None:
        """
        Finds today's value of a stat for a pitcher.

        Args:
            stat_key (str): The key of the stat to find.
            pitcher_id (int): The MLB player ID for the pitcher.
            pitching_stats (list[dict[str, Any]]): A list of dictionaries with pitching stats.

        Returns:
            The stat value as a string, or None if the pitcher is not found.
        """
        # Find the dictionary where 'player_id' matches the pitcher_id
        pitcher_data: dict[str, Any] = next((p for p in pitching_stats if p.get('xMLBAMID') == pitcher_id), None)

        # Return the stat value if the pitcher was found, otherwise return None
        return pitcher_data.get(stat_key) if pitcher_data else None

    def get_off_war_leaders(self) -> list[dict[str, Any]] | None:
        """
        Get today's offensive WAR leaders

        Returns:
            list[dict[str, Any]]: list of offensive WAR leaders
        """
        try:
            storage_service: StorageService = StorageService()  # Create StorageService instance
            batting_blob: bytes = storage_service.get_blob('batting.json').download_blob().readall()  # Get blob
            batting: list[dict[str, Any]] = json.loads(batting_blob).get("data")  # Convert blob to list

        except Exception as err:  # If error, log and return
            logging.error(err)
            return None

        off_war_leaders: list[dict[str, Any]] = []  # List for WAR leaders

        for batter in batting[:25]:  # For each batter
            leader = {  # Create leader dict
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

            off_war_leaders.append(leader)  # Add leader dict to list

        return off_war_leaders
