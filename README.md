# MLB Today API

Python Azure Function to retrieve and store daily Major League Baseball (MLB) probable pitchers and league leaders.

Data is stored in Azure Blob Storage, and each function's data is overwritten every time the function runs.

## Functions

*   `bp_probables`: Fetches today's game schedules and pitching probables from MLB.com.
*   `bp_batting`: Fetches current batting statistics from Fangraphs.
*   `bp_pitching`: Fetches current pitching statistics from Fangraphs.

## Technology Stack

*   **Backend:** Python
*   **Framework:** Azure Functions
*   **Storage:** Azure Blob Storage
*   **HTTP Client:** Requests

## License

This project is licensed under the MIT License. See the LICENSE.md file for details.Copyright (c) 2025

## Disclaimer

This project retrieves data from MLB.com and Fangraphs.com. However, this project is not affiliated with, endorsed by, or in any way officially connected with Major League Baseball or Fangraphs.