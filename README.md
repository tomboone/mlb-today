# MLB Today

Azure Function to retrieve today's Major League Baseball (MLB) schedule w/pitching probables and current stat leaders, then send an email 30 minutes prior to the day's first game.

## Functions

*   `earliest_game_time` (timer trigger): Sets time that email will be sent (30 minutes prior to first game of the day, per MLB.com)
*   `get_batting_stats:`: (timer trigger) Fetches current batting leaders from Fangraphs.
*   `get_pitching_stats`: (timer trigger) Fetches current pitching leaders from Fangraphs.
*   `get_probables`: (timer trigger) Compiles today's probables and leaders data for email and stores in blob.
*   `create_and_send_email`: (blob trigger) On new blob storage, generates an HTML email body from a Jinja2 template, and sends the email.

## Technology Stack

*   **Backend:** Python
*   **Framework:** Azure Functions
*   **Storage:** Azure Blob Storage
*   **Email:** Azure Communication Service
*   **HTTP Client:** Requests

## Required Environment Variables

*   `STORAGE_CONNECTION_STRING`: Azure Blob Storage connection string
*   `BLOB_CONTAINER_NAME`: Azure Blob Storage container name for player statistics
*   `EMAIL_BLOB_CONTAINER_NAME`: Azure Blob Storage container name for probables email data
*   `SUBSCRIPTION_ID`: ID of Azure subscription the app belongs to
*   `TARGET_RESOURCE_GROUP_NAME`: Name of Azure resource group containing the app
*   `TARGET_FUNCTION_APP_NAME`: Name of the Azure Function where this code is deployed
*   `ACS_CONNECTION_STRING`: Connection string for the Azure Communication Service used to send email
*   `ACS_SENDER_ADDRESS`: The sender email address configured for the ACS domain
*   `PROBABLES_TO_EMAIL_STR`: Email address or comma-separated list of email addresses to receive email
*   `PITCHING_CRON`: nCron string for timer trigger to retrieve pitching stats from Fangraphs
*   `BATTING_CRON`: nCron string for timer trigger to retrieve batting stats from Fangraphs
*   `PROBABLES_CRON`: placeholder nCron string for timer trigger to send email (automatically updated daily)
*   `SCHEDULE_CRON`: nCron string for timer trigger to retrieve game schedule for the day from MLB.com

## License

This project is licensed under the MIT License. See the LICENSE.md file for details.Copyright (c) 2025

## Disclaimer

This project retrieves data from MLB.com and Fangraphs.com. However, this project is not affiliated with, endorsed by, or in any way officially connected with Major League Baseball or Fangraphs.