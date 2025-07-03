""" Retrieve pitching stats from Fangraphs """
from datetime import datetime
import json

import azure.functions as func

import src.mlb_today.config as config
from src.mlb_today.services.fangraphs_service import FangraphsService
from src.mlb_today.services.storage_service import StorageService

bp = func.Blueprint()

PITCHING_CRON = config.PITCHING_CRON


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
    # Get pitching stats from Fangraphs
    fangraphs_service = FangraphsService()
    pitching = fangraphs_service.get_data("all", "pit", datetime.now().strftime("%Y"), "default", "WAR")

    # Store pitching stats in Azure Blob
    storage_service = StorageService()
    storage_service.save_blob("pitching.json", json.dumps(pitching))
