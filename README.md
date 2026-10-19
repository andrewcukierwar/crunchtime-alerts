# Crunchtime Alerts

Crunchtime Alerts is a Python-based project designed to provide real-time notifications for NBA games. It leverages the NBA API to fetch game data, calculates Elo ratings for teams, and determines the watchability of games. Alerts are sent via Slack to notify users of exciting game moments, such as close scores in the final minutes or overtime.

## Features

- **Real-time Game Data**: Fetches live NBA game data via ESPN's hidden API.
- **Elo Ratings Calculation**: Computes updated Elo ratings using FiveThirtyEight's original NBA Elo methodology for teams based on game results found using the NBA API.
- **Watchability Scores**: Determines the watchability of games based on team ratings and user preferences.
- **Slack Notifications**: Sends alerts to a Slack channel for key game moments.
- **Daily Reports**: Generates and sends a daily report of all NBA games with their watchability scores.

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/crunchtime-alerts.git
    cd crunchtime-alerts
    ```

2. Install the project dependencies with uv:
    ```sh
    uv sync
    ```

3. Set up your Slack bot token:
    ```sh
    cp .env.example .env
    ```
    Then open `.env` and replace the placeholder with your bot token:
    ```
    SLACK_BOT_TOKEN=xoxb-your-token-here
    ```
    To avoid exposing the token in shell history, export it from your shell profile instead of passing it inline.

## Usage

To run the Crunchtime Alerts script, simply execute the `main.py` file:
```sh
uv run main.py
```

You can also run any of the Python scripts through the same managed environment:
```sh
uv run python nba_elo.py
```

## Project Structure

```
crunchtime-alerts/
├── .env.example
├── .env             # gitignored — create from .env.example
├── .gitignore
├── main.py
├── nba_alerts.py
├── nba_elo.py
├── nba_teams.csv
├── nba_watchability.py
├── pyproject.toml
├── README.md
├── requirements.txt
└── uv.lock
```

## Key Modules
* main.py: The main script that initializes the Slack client, sets up games, and sends alerts.
* nba_alerts.py: Handles fetching game data, updating game states, and sending alerts.
* nba_elo.py: Contains functions for calculating Elo ratings for NBA teams.
* nba_watchability.py: Determines the watchability of games based on team ratings and user preferences.

## Contributing
Contributions are welcome! Please fork the repository and create a pull request with your changes.

## Acknowledgements
* ESPN API for providing access to live NBA game [scores](http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard).
* [NBA API](https://github.com/swar/nba_api) for providing access to NBA game data.
* [Slack API](https://api.slack.com/) for enabling real-time notifications.
* FiveThirtyEight for detailing their original NBA Elo calculation [methodology](https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings/).
* Special thanks to [Allen Hao](https://github.com/allenhao1) for his integral contribution to the favorite teams section.

## Contact
For any questions or suggestions, please open an issue or contact the project maintainer at andrew.cukierwar@gmail.com.
