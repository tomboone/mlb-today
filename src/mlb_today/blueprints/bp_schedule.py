""" Azure Function to compile today's schedule """
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.mlb_today.services.app_setting_service import AppSettingService
from src.mlb_today.services.schedule_service import ScheduleService

import azure.functions as func

import src.mlb_today.config as config
from src.mlb_today.services.mlbdotcom_service import MlbDotComService

bp: func.Blueprint = func.Blueprint()

SCHEDULE_CRON: str = config.SCHEDULE_CRON


# noinspection PyUnusedLocal
@bp.function_name("earliest_game_time")
@bp.timer_trigger(
    arg_name="schedulearg",
    schedule=SCHEDULE_CRON,
    run_on_startup=False
)
def main(schedulearg: func.TimerRequest) -> None:
    """
    Azure function to set schedule for bp_probables based on earliest game start time

    Args:
        schedulearg (func.TimerRequest): timer trigger
    """
    eastern_tz = ZoneInfo("America/New_York")
    today_eastern_str = datetime.now(eastern_tz).strftime("%Y-%m-%d")
    logging.info(f"Checking for games on {today_eastern_str} (Eastern Time).")

    mlbdotcom_service: MlbDotComService = MlbDotComService()  # Create MlbDotComService instance
    games: list[dict[str, str]] | None = mlbdotcom_service.get_schedule(  # Get today's games
        date=today_eastern_str
    )

    if not games:  # If no games found, log and return
        logging.info("No games scheduled for today")
        return

    schedule_service: ScheduleService = ScheduleService()  # Create ScheduleService instance
    new_cron_schedule: str | None = schedule_service.create_new_cron_schedule(games)  # Get new cron schedule

    if not new_cron_schedule:  # If no new cron schedule, log and return
        logging.warning("Failed to generate a new CRON schedule")
        return

    app_settings_service: AppSettingService = AppSettingService()  # Create AppSettingService instance
    app_settings_service.update_setting("PROBABLES_CRON", new_cron_schedule)  # Update app setting
    logging.info(f"NCronTab schedule updated to {new_cron_schedule}")
    return
