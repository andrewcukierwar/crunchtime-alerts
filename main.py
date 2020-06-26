from time import time, sleep
from slack import WebClient
import requests
import nba_alerts
import mlb_alerts

def main():
    bot_token = 'xoxb-828847192688-830705141863-i4aBLMnet30NtN2u0trVcEfF'
    client = WebClient(token=bot_token)

    # initialize nba

    nba_games = nba_alerts.set_games()
    nba_alerted = set()

    nba_daily_report = nba_alerts.get_daily_report(nba_games)
    response = client.chat_postMessage(channel='#crunchtime-alerts', text=nba_daily_report)
    print('NBA Daily Report Sent')

    # initialize mlb

    mlb_games = mlb_alerts.set_games()
    mlb_alerted = set()

    mlb_daily_report = mlb_alerts.get_daily_report(mlb_games)
    response = client.chat_postMessage(channel='#crunchtime-alerts', text=mlb_daily_report)
    print('MLB Daily Report Sent')

    # listen for new alerts

    while True:
        nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted)
        mlb_games, mlb_alerted = mlb_alerts.send_alerts(client, mlb_games, mlb_alerted)
        sleep(60 - time() % 60)

if __name__ == "__main__":
 	main()