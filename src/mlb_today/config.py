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


def get_azure_app_info() -> dict[str, str]:
    """

    Returns:

    """
    # Fallback app values
    subscription_id = os.getenv("SUBSCRIPTION_ID", None)
    resource_group_name = os.getenv("RESOURCE_GROUP_NAME", None)
    app_name = os.getenv("WEBSITE_SITE_NAME", os.getenv("APP_NAME", ""))

    # Get Subscription ID and Resource Group from WEBSITE_OWNER_NAME
    website_owner_name = os.environ.get('WEBSITE_OWNER_NAME')
    if website_owner_name:
        parts = website_owner_name.split('+')
        if len(parts) > 0:
            subscription_id = parts[0]
        if len(parts) > 1:
            resource_group_region_parts = parts[1].split('-')
            if len(resource_group_region_parts) > 2 and \
               resource_group_region_parts[-1] in ['eastus', 'westus', 'centralus', 'northeurope', 'westeurope', 'southeastasia', 'uksouth', 'canadacentral', 'brazilsouth', 'australiaeast', 'japaneast', 'southindia', 'uaenorth', 'southafricanorth', 'koreacentral', 'francecentral', 'germanywestcentral', 'norwayeast', 'switzerlandnorth', 'qatarcentral', 'swedencentral', 'israelcentral', 'polandcentral', 'italycentral', 'newzealandnorth']:
                resource_group_name = "-".join(resource_group_region_parts[:-1])
            else:
                resource_group_name = parts[1] # Fallback if no clear region suffix

    return {
        "app_name": app_name,
        "subscription_id": subscription_id,
        "resource_group_name": resource_group_name
    }