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

2. Create and activate a virtual environment:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

4. Set up your Slack bot token in `:
[config.py    ](http://_vscodecontentref_/1)``python
    # [config.py](http://_vscodecontentref_/2)
    bot_token = 'your-slack-bot-token'
    ```

## Usage

To run the Crunchtime Alerts script, simply execute the `main.py` file:
```sh
python main.py
```

## Project Structure

crunchtime-alerts/
├── .gitignore
├── config.py
├── main.py
├── nba_alerts.py
├── nba_elo.py
├── nba_teams.csv
├── nba_watchability.py
├── README.md
└── requirements.txt

## Key Modules
* main.py: The main script that initializes the Slack client, sets up games, and sends alerts.
* nba_alerts.py: Handles fetching game data, updating game states, and sending alerts.
* nba_elo.py: Contains functions for calculating Elo ratings for NBA teams.
* nba_watchability.py: Determines the watchability of games based on team ratings and user preferences.

## Contributing
Contributions are welcome! Please fork the repository and create a pull request with your changes.

## Acknowledgements
* NBA API for providing access to NBA game data.
* Slack API for enabling real-time notifications.
* Allen Hao for his contribution to the favorite teams section.

## Contact
For any questions or suggestions, please open an issue or contact the project maintainer at andrew.cukierwar@gmail.com.