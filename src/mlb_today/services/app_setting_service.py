""" Azure App Settings service """
import logging

from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.web.v2018_02_01.models import StringDictionary

import src.mlb_today.config as config

SUBSCRIPTION_ID: str = config.SUBSCRIPTION_ID
TARGET_RESOURCE_GROUP: str = config.TARGET_RESOURCE_GROUP_NAME
TARGET_FUNCTION_APP_NAME: str = config.TARGET_FUNCTION_APP_NAME


# noinspection PyTypeChecker
class AppSettingService:
    """ Azure App Settings service """
    def __init__(self):
        self.subscription_id = SUBSCRIPTION_ID
        self.target_resource_group = TARGET_RESOURCE_GROUP
        self.target_function_app_name = TARGET_FUNCTION_APP_NAME

    def update_setting(self, setting_name: str, setting_value: str) -> None:
        """
        Update app setting

        Args:
            setting_name (str): setting name
            setting_value (str): setting value
        """
        try:
            credential: DefaultAzureCredential = DefaultAzureCredential()  # Create DefaultAzureCredential instance
            web_client: WebSiteManagementClient = WebSiteManagementClient(credential, SUBSCRIPTION_ID)  # Create client

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
            logging.error(err)
            return

        return
