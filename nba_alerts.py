from datetime import timedelta, datetime as dt
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
        if 'espn' in url:
            continue
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
    new_alerts = {'5 Min': set(), '1 Min': set(), 'OT': set()}
    for teams, game in games.items():
        differential = abs(game['score'][0] - game['score'][1])
        if teams not in alerted['5 Min'] and game['quarter'] == 4 and game['clock'] <= 300 and differential <= 5:
            new_alerts['5 Min'].add(teams)
        if teams not in alerted['1 Min'] and game['quarter'] == 4 and game['clock'] <= 60 and differential <= 3:
            new_alerts['1 Min'].add(teams)
        if teams not in alerted['OT'] and game['quarter'] == 5: # if game['quarter'] >= 5 and game['clock'] == 300
            new_alerts['OT'].add(teams)
    return new_alerts

def get_daily_report(games):
    ratings = nba_watchability.get_team_ratings()
    watchability_dict = nba_watchability.get_watchability(ratings)
    for game in games:
        games[game].update(watchability_dict[game])
    all_text = []
    for (away_team, home_team), game in games.items():
        text = '<%s|%s @ %s at %s>\n%s Watchability' % (game['url'], away_team, home_team, 
            game['time'], game['Watchability'])
        all_text.append(text)
    daily_report = '\n\n'.join(all_text)
    return daily_report

def send_alerts(client, games, alerted):
    games = update_games(games)
    new_alerts = check_for_new_alerts(games, alerted)
    for timeframe, all_teams in new_alerts.items():
        for teams in all_teams:
            game = games[teams]
            away_team, home_team = teams
            away_score, home_score = game['score']
            text = '<%s|%s %s, %s %s. %s remaining>' % (game['url'], away_team, away_score, 
            	home_team, home_score, game['displayClock'])
            response = client.chat_postMessage(channel='#bot-testing', text=text) ## CHANGE BACK
            print('Alert Sent')
            alerted[timeframe].add(teams)
    return games, alerted

def get_time_windows(games):
    today = dt.now().date()
    first_game_time = list(games.values())[0]['time'].split()[0]
    lower_window = dt.combine(today, dt.strptime(first_game_time, '%I:%M%p').time())
    return lower_window

def is_completed(games):
    for game in games.values():
        if game['quarter'] < 4 or game['clock'] != 0 or game['score'][0] == game['score'][1]:
            return False
    return True

def get_score_report(games):
    all_text = []
    for (away_team, home_team), game in games.items():
        away_score, home_score = game['score']
        text = '<%s|%s %s, %s %s with %s remaining in Q%s>' % (game['url'], away_team, 
            away_score, home_team, home_score, game['displayClock'], game['quarter'])
        if away_score + home_score == 0: # game hasn't started
            text = '<%s|%s @ %s at %s>\n%s Watchability' % (game['url'], away_team, home_team, 
                game['time'], game['Watchability'])
        elif game['quarter'] >= 4 and game['clock'] == 0 and away_score != home_score: # game completed
            text = '%s %s, %s %s' % (away_team, away_score, home_team, home_score)
        all_text.append(text)
    score_report = '\n\n'.join(all_text)
    return score_report
