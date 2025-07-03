""" Service for retrieving/parsing today's schedule """
import logging
from datetime import datetime, timedelta, timezone
from typing import Any


# noinspection PyMethodMayBeStatic
class ScheduleService:
    """ Service for retrieving/parsing today's schedule """
    def create_new_cron_schedule(self, games: list[dict[str, Any]]) -> str:
        """
        Create probables cron schedule based on earliest game time

        Args:
            games:

        Returns:

        """
        earliest_game: dict[str, Any] = min(games, key=lambda game: game.get("gameDate"))  # Find earliest game
        earliest_time_str: str = earliest_game.get("gameDate")

        new_cron_schedule: str | None = self.create_utc_ncron_from_timestring(earliest_time_str, subtract_minutes=30)

        return new_cron_schedule

    def create_utc_ncron_from_timestring(self, iso_timestring: str, subtract_minutes: int = 0) -> str | None:
        """
        Converts an ISO 8601 timestring to a UTC-based NCronTab string, subtracting a given number of minutes.

        Args:
            iso_timestring: The input time string (e.g., '2025-07-03T12:10:00-04:00' or '2024-07-20T17:05:00Z').
            subtract_minutes: The number of minutes to subtract from the time before conversion.

        Returns:
            An NCronTab string in the format "second minute hour day month *" or None on failure.
        """
        if not iso_timestring:
            return None
        try:
            # Parse the ISO 8601 string into a timezone-aware datetime object.
            dt_aware: datetime = datetime.fromisoformat(iso_timestring.replace('Z', '+00:00'))

            # Subtract the specified number of minutes.
            dt_adjusted: datetime = dt_aware - timedelta(minutes=subtract_minutes)

            # Convert the resulting datetime object to UTC to normalize it.
            dt_utc: datetime = dt_adjusted.astimezone(timezone.utc)

            # Format into an NCronTab string: {second} {minute} {hour} {day} {month} {day of week}
            ncrontab: str = f"0 {dt_utc.minute} {dt_utc.hour} * * *"

            return ncrontab

        except (ValueError, TypeError) as e:  # If error, log and return None
            logging.error(f"Could not parse or convert timestring '{iso_timestring}': {e}")
            return None