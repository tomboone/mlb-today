""" Retrieve pitching probables from MLB.com """
import json
import logging
from datetime import datetime
from typing import Any

import azure.functions as func

import src.mlb_today.config as config
from src.mlb_today.services.mlbdotcom_service import MlbDotComService
from src.mlb_today.services.probables_service import ProbablesService
from src.mlb_today.services.storage_service import StorageService

bp: func.Blueprint = func.Blueprint()

PROBABLES_CRON: str = config.PROBABLES_CRON
EMAIL_BLOB_CONTAINER_NAME: str = config.EMAIL_BLOB_CONTAINER_NAME


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
    mlbdotcom_service: MlbDotComService = MlbDotComService()  # Create MlbDotComService instance
    probables: list[dict[str, Any]] | None = mlbdotcom_service.get_schedule(  # Get today's pitching probables
        date=datetime.now().strftime("%Y-%m-%d")
    )

    if not probables:  # If no probables found, log and return
        logging.info("No probables found for today")
        return

    probables_service: ProbablesService = ProbablesService()  # Create ProbablesService instance
    probables_data: list[dict[str, Any]] | None = probables_service.get_probables_data(  # Get probables data
        probables=probables
    )
    batting_data: list[dict[str, Any]] | None = probables_service.get_off_war_leaders()  # Get batting data
    pitching_data: list[dict[str, Any]] | None = probables_service.get_pitching_war_leaders()  # Get pitching data

    email_data: dict[str, Any] = {  # Create email data
        "probables": probables_data,
        "batting": batting_data,
        "pitching": pitching_data
    }

    storage_service: StorageService = StorageService()  # Create StorageService instance
    logging.info(f"Saving email data to {EMAIL_BLOB_CONTAINER_NAME}/email_data.json")
    storage_service.save_blob(  # Store email data in Azure Blob
        blob_filename="email_data.json",  # Use a consistent filename
        data=json.dumps(email_data, indent=4),  # Use indent for readability
        blob_container_name=EMAIL_BLOB_CONTAINER_NAME
    )
