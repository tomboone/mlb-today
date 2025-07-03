""" Retrieve batting stats from Fangraphs """
from datetime import datetime
import json
from typing import Any

import azure.functions as func

import src.mlb_today.config as config
from src.mlb_today.services.fangraphs_service import FangraphsService
from src.mlb_today.services.storage_service import StorageService

bp: func.Blueprint = func.Blueprint()

BATTING_CRON: str = config.BATTING_CRON


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
    fangraphs_service: FangraphsService = FangraphsService()  # Create FangraphsService instance
    batting: dict[str, Any] = fangraphs_service.get_data(  # Get batting stats from Fangraphs
        position="all",
        stats_type="bat",
        year=datetime.now().strftime("%Y"),
        sort_dir="default",
        sort_stat="WAR"
    )

    storage_service: StorageService = StorageService()  # Create StorageService instance
    storage_service.save_blob(  # Store batting stats in Azure Blob
        blob_filename="batting.json",
        data=json.dumps(batting)
    )

    return
