from datetime import datetime as dt
from time import time, sleep
from slack import WebClient
import requests
import nba_alerts
# import mlb_alerts
import config

def main():
    client = WebClient(token=config.bot_token)

    # initialize nba

    nba_games = nba_alerts.set_games()
    nba_alerted = {'5 Min': set(), '1 Min': set(), 'OT': set()}

    nba_daily_report = nba_alerts.get_daily_report(nba_games)
    response = client.chat_postMessage(channel='#crunchtime-alerts', text=nba_daily_report)
    print('NBA Daily Report Sent')

    lower_window = nba_alerts.get_time_windows(nba_games)

    # initialize mlb

    ## mlb_games = mlb_alerts.set_games()
    ## mlb_alerted = set()

    ## mlb_daily_report = mlb_alerts.get_daily_report(mlb_games)
    ## response = client.chat_postMessage(channel='#crunchtime-alerts', text=mlb_daily_report)
    ## print('MLB Daily Report Sent')

    # listen for new alerts

    while dt.now() < lower_window: # check every 30 minutes
        print('Checking to see if first game started')
        interval = 30 * 60 # 30 minute intervals
        sleep(interval - time() % interval)

    print('First game started')

    nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted)

    while not nba_alerts.is_completed(nba_games):
        nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted)
        ## mlb_games, mlb_alerted = mlb_alerts.send_alerts(client, mlb_games, mlb_alerted)
        sleep(60 - time() % 60)

    print('All games done')

    return

if __name__ == "__main__":
 	main()