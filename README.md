# MLB Today

Azure Function to retrieve today's Major League Baseball (MLB) schedule w/pitching probables and current stat leaders, then send an email 30 minutes prior to the day's first game.

## Trigger Functions

*   `earliest_game_time` (timer): Sets time that email will be sent (30 minutes prior to first game of the day, per MLB.com)
*   `get_batting_stats:`: (timer) Fetches current batting leaders from Fangraphs.
*   `get_pitching_stats`: (timer) Fetches current pitching leaders from Fangraphs.
*   `get_probables`: (timer) Compiles today's probables and leaders data for email and stores in blob.
*   `create_and_send_email`: (blob) On new blob storage, generates an HTML email body from a Jinja2 template, and sends the email.

## Technology Stack

*   **Backend:** Python
*   **Framework:** Azure Functions
*   **Storage:** Azure Blob Storage
*   **Email:** Azure Communication Service
*   **HTTP Client:** Requests

## Required Environment Variables

*   `SCHEDULE_ENDPOINT`: URL for MLB.com schedule API
*   `STATS_ENDPOINT`: URL for Fangraphs stat leaders API
*   `LOG_DIRECTORY`: Directory for log files
*   `LOG_LEVEL`: Log level for logging
*   `PITCHING_CRON`: nCron string for timer trigger to retrieve pitching stats from Fangraphs
*   `BATTING_CRON`: nCron string for timer trigger to retrieve batting stats from Fangraphs
*   `PROBABLES_CRON`: placeholder nCron string for timer trigger to send email (automatically updated daily)
*   `SCHEDULE_CRON`: nCron string for timer trigger to retrieve game schedule for the day from MLB.com
*   `STORAGE_CONNECTION_STRING`: Azure Blob Storage connection string
*   `BLOB_CONTAINER_NAME`: Azure Blob Storage container name for player statistics
*   `EMAIL_BLOB_CONTAINER_NAME`: Azure Blob Storage container name for probables email data
*   `ACS_CONNECTION_STRING`: Connection string for the Azure Communication Service used to send email
*   `ACS_SENDER_ADDRESS`: The sender email address configured for the ACS domain
*   `PROBABLES_TO_EMAIL_STR`: Email address or comma-separated list of email addresses to receive email

## Development Environment Variables (for testing `earliest_game_time` function)
  
*   `SUBSCRIPTION_ID`: ID of Azure subscription the production app belongs to
*   `TARGET_RESOURCE_GROUP_NAME`: Name of Azure resource group containing the production app
*   `TARGET_FUNCTION_APP_NAME`: Name of the Azure Function where this code is deployed to production

## Optional Environment Variable:

*   `DISABLE_EMAIL_SENDING`: Set to `True` to disable daily email (e.g., in staging deployment slot)

## License

This project is licensed under the MIT License. See the LICENSE.md file for details.Copyright (c) 2025

## Disclaimer

This project retrieves data from MLB.com and Fangraphs.com. However, this project is not affiliated with, endorsed by, or in any way officially connected with Major League Baseball or Fangraphs.