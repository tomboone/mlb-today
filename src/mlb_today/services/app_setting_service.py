""" Azure App Settings service """
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient

import src.mlb_today.config as config
from src.mlb_today.logger import logger

# noinspection PyTypeChecker,PyMethodMayBeStatic
class AppSettingService:
    """ Azure App Settings service """
    def __init__(
        self,
        subscription_id: str,
        target_resource_group: str,
        target_function_app_name: str,
        target_slot_name: str | None = None
    ):
        self.subscription_id = subscription_id
        self.target_resource_group = target_resource_group
        self.target_function_app_name = target_function_app_name
        self.target_slot_name = target_slot_name

    def update_setting(self, setting_name: str, setting_value: str) -> None:
        """
        Update app setting for the production slot or a specific deployment slot.

        Args:
            setting_name (str): setting name
            setting_value (str): setting value
        """
        try:
            credential: DefaultAzureCredential = DefaultAzureCredential()
            web_client: WebSiteManagementClient = WebSiteManagementClient(credential, self.subscription_id)

            # If a slot name is provided, use the slot-specific SDK methods
            if self.target_slot_name:
                logger.info(f"Updating setting for slot: '{self.target_slot_name}'")
                current_settings = web_client.web_apps.list_application_settings_slot(
                    resource_group_name=self.target_resource_group,
                    name=self.target_function_app_name,
                    slot=self.target_slot_name
                )
                current_settings.properties[setting_name] = setting_value
                web_client.web_apps.update_application_settings_slot(
                    resource_group_name=self.target_resource_group,
                    name=self.target_function_app_name,
                    app_settings=current_settings,
                    slot=self.target_slot_name
                )
            # Otherwise, update the production slot
            else:
                logger.info("Updating setting for production slot.")
                current_settings = web_client.web_apps.list_application_settings(
                    resource_group_name=self.target_resource_group,
                    name=self.target_function_app_name
                )
                current_settings.properties[setting_name] = setting_value
                web_client.web_apps.update_application_settings(
                    resource_group_name=self.target_resource_group,
                    name=self.target_function_app_name,
                    app_settings=current_settings
                )

        except Exception as err:
            logger.error(err)
            return

        return

def get_azure_app_info() -> dict[str, str | None]:
    """
    Get Azure App Info, including the current deployment slot name.

    Returns:
        A dictionary containing app_name, subscription_id, resource_group_name, and slot_name.
    """
    app_name = os.getenv("WEBSITE_SITE_NAME", config.TARGET_FUNCTION_APP_NAME)
    resource_group_name = os.getenv("WEBSITE_RESOURCE_GROUP", config.TARGET_RESOURCE_GROUP_NAME)

    # Get the current slot name from the environment variable
    slot_name = os.getenv("WEBSITE_SLOT_NAME")

    # The SDK methods for the production slot don't take a 'slot' parameter.
    # If the slot name is 'production', we treat it as None.
    if slot_name and slot_name.lower() == "production":
        slot_name = None

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
        "resource_group_name": resource_group_name,
        "slot_name": slot_name
    }