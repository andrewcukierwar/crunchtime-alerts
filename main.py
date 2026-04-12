import logging
import os
import sys
from datetime import datetime as dt
from logging.handlers import RotatingFileHandler
from time import time, sleep
from slack_sdk import WebClient
import nba_alerts

def main():
    handler_file = RotatingFileHandler('crunchtime.log', maxBytes=1_000_000, backupCount=3)
    handler_console = logging.StreamHandler()
    fmt = '%(asctime)s %(levelname)s %(message)s'
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[handler_file, handler_console])

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("Error: SLACK_BOT_TOKEN is not set. See .env.example for setup instructions.")
    if not token.startswith("xoxb-"):
        sys.exit("Error: SLACK_BOT_TOKEN does not look like a Slack bot token (expected xoxb-...). Check .env.example.")
    client = WebClient(token=token)

    nba_games = nba_alerts.set_games()
    nba_alerted = {'5 Min': set(), '1 Min': set(), 'OT': set()}

    nba_daily_report = nba_alerts.get_daily_report(nba_games)
    response = client.chat_postMessage(channel='#crunchtime-alerts', text=nba_daily_report)
    logging.info('NBA daily report sent')

    lower_window = nba_alerts.get_time_windows(nba_games)

    # listen for new alerts

    while dt.now() < lower_window: # check every 30 minutes
        logging.info('Waiting for first game to start')
        interval = 30 * 60 # 30 minute intervals
        sleep(interval - time() % interval)

    logging.info('First game started')

    nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted)

    while not nba_alerts.is_completed(nba_games):
        nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted)
        sleep(60 - time() % 60)

    logging.info('All games completed')

    return

if __name__ == "__main__":
 	main()
