""" Retrieve batting stats from Fangraphs """
from datetime import datetime
import json

import azure.functions as func

import src.mlb_today.config as config
from src.mlb_today.services.fangraphs_service import FangraphsService
from src.mlb_today.services.storage_service import StorageService

bp = func.Blueprint()

BATTING_CRON = config.BATTING_CRON


# noinspection PyUnusedLocal
@bp.function_name(name="get_batting_stats")
@bp.timer_trigger(
    arg_name="battingarg",
    schedule=BATTING_CRON,
    run_on_startup=False
)
def main(battingarg: func.TimerRequest) -> None:
    """
    Azure Function to retrieve batting stats from Fangraphs

    Args:
        battingarg (func.TimerRequest): timer trigger
    """
    # Get batting stats from Fangraphs
    fangraphs_service = FangraphsService()
    batting = fangraphs_service.get_data("all", "bat", datetime.now().strftime("%Y"), "default", "WAR")

    # Store batting stats in Azure Blob
    storage_service = StorageService()
    storage_service.save_blob("batting.json", json.dumps(batting))
