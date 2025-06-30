# MLB Today API

Python Azure Function to retrieve and store daily Major League Baseball (MLB) probable pitchers and league leaders.

Data is stored in Azure Blob Storage, and each function's data is overwritten every time the function runs.

## Functions

*   `get_probables`: Fetches today's games and pitching probables from MLB.com.
*   `get_batting_stats:`: Fetches current batting leaders from Fangraphs.
*   `get_pitching_stats`: Fetches current pitching leaders from Fangraphs.

## Technology Stack

*   **Backend:** Python
*   **Framework:** Azure Functions
*   **Storage:** Azure Blob Storage
*   **HTTP Client:** Requests

## Required Environment Variables

*   `STORAGE_CONNECTION_STRING`: Azure Blob Storage connection string
*   `BLOB_CONTAINER_NAME`: Azure Blob Storage container name
*   `PITCHING_CRON`: timer trigger nCron string for `get_pitching_stats`
*   `BATTING_CRON`: timer triggernCron string for `get_batting_stats`
*   `PROBABLES_CRON`: timer triggernCron string for `get_probables`

## License

This project is licensed under the MIT License. See the LICENSE.md file for details.Copyright (c) 2025

## Disclaimer

This project retrieves data from MLB.com and Fangraphs.com. However, this project is not affiliated with, endorsed by, or in any way officially connected with Major League Baseball or Fangraphs.