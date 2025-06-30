""" Retrieve pitching probables from MLB.com """
from datetime import datetime

import azure.functions as func

import src.mlb_today.config as config
from src.mlb_today.services.mlbdotcom_service import MlbDotComService
from src.mlb_today.services.storage_service import StorageService

bp = func.Blueprint()

PROBABLES_CRON = config.PROBABLES_CRON


# noinspection PyUnusedLocal
@bp.function_name(name="get_probables")
@bp.timer_trigger(
    arg_name="probablesarg",
    schedule=PROBABLES_CRON,
    run_on_startup=False
)
def main(probablesarg: func.TimerRequest) -> None:
    """
    Azure Function to retrieve pitching probables from MLB.com

    Args:
        probablesarg (func.TimerRequest): timer trigger
    """
    # Get pitching probables from MLB.com
    mlbdotcom_service = MlbDotComService()
    probables = mlbdotcom_service.get_schedule(datetime.now().strftime("%Y-%m-%d"))

    # Store pitching probables in Azure Blob
    storage_service = StorageService()
    storage_service.save_blob("probables.json", str(probables))
