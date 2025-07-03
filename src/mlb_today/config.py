""" Configuration for mlb-today """
import os

STORAGE_CONNECTION_STRING = os.getenv("STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

PITCHING_CRON = os.getenv("PITCHING_CRON")
BATTING_CRON = os.getenv("BATTING_CRON")
PROBABLES_CRON = os.getenv("PROBABLES_CRON")
SCHEDULE_CRON = os.getenv("SCHEDULE_CRON")


SCHEDULE_ENDPOINT = "https://statsapi.mlb.com/api/v1/schedule"
STATS_ENDPOINT = "https://www.fangraphs.com/api/leaders/major-league/data"
