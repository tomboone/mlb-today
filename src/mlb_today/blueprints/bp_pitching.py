""" Retrieve pitching stats from Fangraphs """
from datetime import datetime
import json
from typing import Any

import azure.functions as func

import src.mlb_today.config as config
from src.mlb_today.services.fangraphs_service import FangraphsService
from src.mlb_today.services.storage_service import StorageService

bp: func.Blueprint = func.Blueprint()

PITCHING_CRON: str = config.PITCHING_CRON


# noinspection PyUnusedLocal
@bp.function_name(name="get_pitching_stats")
@bp.timer_trigger(
    arg_name="pitchingarg",
    schedule=PITCHING_CRON,
    run_on_startup=False
)
def main(pitchingarg: func.TimerRequest) -> None:
    """
    Azure Function to retrieve pitching stats from Fangraphs

    Args:
        pitchingarg (func.TimerRequest): Timer Trigger
    """
    fangraphs_service: FangraphsService = FangraphsService()  # Create FangraphsService instance
    pitching: dict[str, Any] = fangraphs_service.get_data(  # Get pitching stats from Fangraphs
        position="all",
        stats_type="pit",
        year=datetime.now().strftime("%Y"),
        sort_dir="default",
        sort_stat="WAR")

    storage_service: StorageService = StorageService()  # Create StorageService instance
    storage_service.save_blob(  # Store pitching stats in Azure Blob
        blob_filename="pitching.json",
        data=json.dumps(pitching)
    )
