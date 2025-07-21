""" Azure App Settings service """
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.web.v2018_02_01.models import StringDictionary

import src.mlb_today.config as config
from src.mlb_today.logger import logger

# noinspection PyTypeChecker,PyMethodMayBeStatic
class AppSettingService:
    """ Azure App Settings service """
    def __init__(self, subscription_id: str, target_resource_group: str, target_function_app_name: str):
        self.subscription_id = subscription_id
        self.target_resource_group = target_resource_group
        self.target_function_app_name = target_function_app_name

    def update_setting(self, setting_name: str, setting_value: str) -> None:
        """
        Update app setting

        Args:
            setting_name (str): setting name
            setting_value (str): setting value
        """
        try:
            credential: DefaultAzureCredential = DefaultAzureCredential()  # Create DefaultAzureCredential instance
            web_client: WebSiteManagementClient = WebSiteManagementClient(credential, self.subscription_id)  # Create client

            current_settings: StringDictionary = web_client.web_apps.list_application_settings(  # Get current settings
                resource_group_name=self.target_resource_group,
                name=self.target_function_app_name
            )

            current_settings.properties[setting_name]: str = setting_value  # Set new setting value

            web_client.web_apps.update_application_settings(  # Update settings
                resource_group_name=self.target_resource_group,
                name=self.target_function_app_name,
                app_settings=current_settings
                )

        except Exception as err:  # If error, log and return
            logger.error(err)
            return

        return

def get_azure_app_info() -> dict[str, str]:
    """
    Get Azure App Info from

    Args:


    Returns:

    """
    app_name = os.getenv("WEBSITE_SITE_NAME", config.TARGET_FUNCTION_APP_NAME)
    resource_group_name = os.getenv("WEBSITE_RESOURCE_GROUP", config.TARGET_RESOURCE_GROUP_NAME)

    # Get Subscription ID from WEBSITE_OWNER_NAME
    subscription_id: str | None = config.SUBSCRIPTION_ID
    website_owner_name = os.environ.get('WEBSITE_OWNER_NAME')
    if website_owner_name:
        parts = website_owner_name.split('+')
        if len(parts) > 0:
            subscription_id = parts[0]

    return {
        "app_name": app_name,
        "subscription_id": subscription_id,
        "resource_group_name": resource_group_name
    }
