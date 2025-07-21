""" Configuration for mlb-today """
import os

STORAGE_CONNECTION_STRING = os.getenv("STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")
EMAIL_BLOB_CONTAINER_NAME = os.getenv("EMAIL_BLOB_CONTAINER_NAME")

SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
TARGET_RESOURCE_GROUP_NAME = os.getenv("TARGET_RESOURCE_GROUP_NAME")
TARGET_FUNCTION_APP_NAME = os.getenv("TARGET_FUNCTION_APP_NAME")

ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING")
ACS_SENDER_ADDRESS = os.getenv("ACS_SENDER_ADDRESS")

PROBABLES_TO_EMAIL_STR = os.getenv("PROBABLES_TO_EMAIL_STR")

PITCHING_CRON = os.getenv("PITCHING_CRON")
BATTING_CRON = os.getenv("BATTING_CRON")
PROBABLES_CRON = os.getenv("PROBABLES_CRON")
SCHEDULE_CRON = os.getenv("SCHEDULE_CRON")


SCHEDULE_ENDPOINT = os.getenv("SCHEDULE_ENDPOINT")
STATS_ENDPOINT = "https://www.fangraphs.com/api/leaders/major-league/data"

LOG_DIRECTORY = os.getenv("LOG_DIRECTORY")
LOG_LEVEL = os.getenv("LOG_LEVEL")

DISABLE_EMAIL_SENDING: bool = False

disable_email: str | None = os.getenv("DISABLE_EMAIL_SENDING")

if disable_email and disable_email.strip().lower() in ("true", "1", "yes", "on"):
    DISABLE_EMAIL_SENDING = True
