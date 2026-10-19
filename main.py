import logging
import os
import sys
from datetime import datetime as dt, timedelta
from logging.handlers import RotatingFileHandler
from time import time, sleep
from requests.exceptions import RequestException
from slack_sdk import WebClient
import nba_alerts

STOP_HOUR = 3 # stop polling at 3 AM the next morning even if a game never reports as finished

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

    slate_date = (dt.now() - timedelta(hours=STOP_HOUR)).date() # before 3 AM, still last night's slate
    try:
        nba_games = nba_alerts.set_games(slate_date)
    except Exception as e:
        logging.error('Failed to fetch games from ESPN: %s', e)
        sys.exit(1)

    if not nba_games:
        logging.info('No NBA games today')
        try:
            client.chat_postMessage(channel='#crunchtime-alerts', text='No NBA games today')
        except Exception as e:
            logging.warning('Failed to post rest-day message: %s', e)
        sys.exit(0)

    nba_alerted = nba_alerts.load_alerted(slate_date)
    if nba_alerted is None:
        nba_alerted = nba_alerts.new_alerted()
        nba_daily_report = nba_alerts.get_daily_report(nba_games)
        try:
            client.chat_postMessage(channel='#crunchtime-alerts', text=nba_daily_report)
            logging.info('NBA daily report sent')
            nba_alerts.save_alerted(nba_alerted, slate_date) # restarts skip the report from here on
        except Exception as e:
            logging.warning('Failed to send daily report: %s', e)
    else:
        logging.info('Daily report already sent for this slate; skipping')

    lower_window = nba_alerts.get_time_windows(nba_games)
    if lower_window is None:
        logging.error('Could not determine game start windows')
        sys.exit(1)

    # listen for new alerts

    while dt.now() < lower_window: # check every 30 minutes
        logging.info('Waiting for first game to start')
        interval = 30 * 60 # 30 minute intervals
        sleep(interval - time() % interval)

    logging.info('First game started')

    cutoff = dt.combine(slate_date, dt.min.time()) + timedelta(days=1, hours=STOP_HOUR)
    while not nba_alerts.is_completed(nba_games):
        if dt.now() >= cutoff:
            logging.warning('Stopping at %s cutoff with games still unfinished', cutoff.strftime('%-I:%M %p'))
            return
        try:
            nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted, slate_date)
        except (RequestException, KeyError, ValueError) as e:
            logging.warning('Error during game update cycle: %s', e)
        sleep(60 - time() % 60)

    logging.info('All games completed')

if __name__ == "__main__":
    main()
