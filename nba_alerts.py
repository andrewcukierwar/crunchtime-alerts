from bs4 import BeautifulSoup
from slack import WebClient
import nba_watchability
import requests

def set_games():
    response = requests.get('http://nbastreams.xyz')
    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.find_all('a', class_ = 'btn btn-default btn-lg btn-block')
    games = {}
    for a_tag in content:
        url = a_tag['href']
        time = a_tag.find('p').text.split(' - ')[1]
        teams = a_tag.find('h4').text.strip().split(' vs ')
        if len(teams) < 2:
            teams = a_tag.find('h4').text.strip().split(' at ')
        away = teams[0].split()[-1]
        home = teams[1].split()[-1]
        games[(away, home)] = {'url':url, 'time':time}
    return games

def update_games(games):
    espn_api = 'http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
    response = requests.get(espn_api)
    data = response.json()
    for event in data['events']:
        home, away = event['competitions'][0]['competitors']
        away_team = away['team']['displayName'].split()[-1]
        home_team = home['team']['displayName'].split()[-1]
        games[(away_team, home_team)].update({
            'score':(int(away['score']), int(home['score'])),
            'quarter':event['status']['period'],
            'clock':event['status']['clock'],
            'displayClock':event['status']['displayClock']
        })
    return games

def check_for_new_alerts(games, alerted):
    new_alerts = set()
    for teams, game in games.items():
        if teams not in alerted and game['quarter'] == 4 and game['clock'] > 0 and game['clock'] <= 300:
            differential = abs(game['score'][0] - game['score'][1])
            if differential <= 5:
                new_alerts.add(teams)
    return new_alerts

def get_daily_report(games):
    ratings = nba_watchability.get_team_ratings()
    watchability_dict = nba_watchability.get_watchability(ratings)
    for game in games:
        games[game].update(watchability_dict[game])
    all_text = []
    for teams, game in games.items():
        text = '<%s|%s @ %s at %s>\n%s Watchability' % (game['url'], teams[0], teams[1], game['time'], game['Watchability'])
        all_text.append(text)
    daily_report = '\n\n'.join(all_text)
    return daily_report

def send_alerts(client, games, alerted):
    games = update_games(games)
    new_alerts = check_for_new_alerts(games, alerted)
    for teams in new_alerts:
        game = games[teams]
        text = '<%s | %s %s, %s %s. %s remaining>' % (game['url'], teams[0], game['score'][0], 
        	teams[1], game['score'][1], game['displayClock'])
        response = client.chat_postMessage(channel='#crunchtime-alerts', text=text)
        print('Alert Sent')
        alerted.add(teams)
    return games, alerted