import logging
from datetime import datetime as dt
import nba_watchability
import requests

CLOCK_ZERO = 0.001  # ESPN returns a small non-zero float for completed games, not exactly 0.0

def set_game_urls(games):
    for game in games.values():
        away_full = game['away_full']
        home_full = game['home_full']
        url1 = 'https://crackstreams.ms/stream/%s-vs-%s' % (away_full, home_full)
        url2 = 'https://crackstreams.ms/stream/%s-vs-%s' % (home_full, away_full)
        try:
            url = url2 if '404 Not Found - CrackStreamsms' in requests.get(url1, timeout=5).text else url1
        except Exception as e:
            logging.warning('Could not fetch stream URL for %s vs %s: %s', away_full, home_full, e)
            url = '#'
        game['url'] = url

def set_games():
    espn_api = 'http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
    response = requests.get(espn_api, timeout=10)
    data = response.json()
    games = {}
    for event in data['events']:
        home, away = event['competitions'][0]['competitors']
        away_team, home_team = nba_watchability.get_team_names(event)
        # keyed by ESPN event id: stable across polls, unlike team names
        games[event['id']] = {
            'away': away_team,
            'home': home_team,
            'time': event['status']['type']['shortDetail'].split('-')[1][1:],
            'away_full': away['team']['displayName'].replace(' ', '-').replace('LA', 'Los-Angeles'),
            'home_full': home['team']['displayName'].replace(' ', '-').replace('LA', 'Los-Angeles'),
            'score': (0, 0),
            'quarter': 0,
            'clock': 9999.0,
            'displayClock': '',
        }
    set_game_urls(games)
    return games

def update_games(games):
    espn_api = 'http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
    response = requests.get(espn_api, timeout=10)
    data = response.json()
    for event in data['events']:
        if event['id'] not in games:
            logging.warning('Skipping unknown game %s (%s)', event['id'], event.get('name'))
            continue
        home, away = event['competitions'][0]['competitors']
        games[event['id']].update({
            'score':(int(away['score']), int(home['score'])),
            'quarter':event['status']['period'],
            'clock':event['status']['clock'],
            'displayClock':event['status']['displayClock']
        })
    return games

def check_for_new_alerts(games, alerted):
    new_alerts = {'5 Min': set(), '1 Min': set(), 'OT': set()}
    for game_id, game in games.items():
        differential = abs(game['score'][0] - game['score'][1])
        if game_id not in alerted['5 Min'] and game['quarter'] == 4 and game['clock'] <= 300 and differential <= 5:
            new_alerts['5 Min'].add(game_id)
        if game_id not in alerted['1 Min'] and game['quarter'] == 4 and game['clock'] <= 60 and differential <= 3:
            new_alerts['1 Min'].add(game_id)
        if game_id not in alerted['OT'] and game['quarter'] == 5: # if game['quarter'] >= 5 and game['clock'] == 300
            new_alerts['OT'].add(game_id)
    return new_alerts

def get_daily_report(games):
    ratings = nba_watchability.get_team_ratings()
    watchability_dict = nba_watchability.get_watchability(ratings)
    default_watchability = {'Watchability': 'Medium', 'Away Rating': 0, 'Home Rating': 0}
    for game in games.values():
        game.update(watchability_dict.get((game['away'], game['home']), default_watchability))
    all_text = []
    for game in games.values():
        text = '<%s|%s @ %s at %s>\n%s Watchability' % (game['url'], game['away'], game['home'], 
            game['time'], game['Watchability'])
        all_text.append(text)
    daily_report = '\n\n'.join(all_text)
    return daily_report

def send_alerts(client, games, alerted):
    games = update_games(games)
    new_alerts = check_for_new_alerts(games, alerted)
    for timeframe, game_ids in new_alerts.items():
        for game_id in game_ids:
            game = games[game_id]
            away_team, home_team = game['away'], game['home']
            away_score, home_score = game['score']
            text = '<%s|%s %s, %s %s. %s remaining>' % (game['url'], away_team, away_score, 
            	home_team, home_score, game['displayClock'])
            try:
                client.chat_postMessage(channel='#crunchtime-alerts', text=text)
                logging.info('Alert sent: %s vs %s (%s)', away_team, home_team, timeframe)
                alerted[timeframe].add(game_id)
            except Exception as e:
                logging.warning('Failed to send alert for %s vs %s (%s): %s', away_team, home_team, timeframe, e)
    return games, alerted

def get_time_windows(games):
    if not games:
        return None
    today = dt.now().date()
    first_game_time = ''.join(list(games.values())[0]['time'].split()[:2])
    lower_window = dt.combine(today, dt.strptime(first_game_time, '%I:%M%p').time())
    return lower_window

def is_completed(games):
    for game in games.values():
        if game['quarter'] < 4 or game['clock'] > CLOCK_ZERO or game['score'][0] == game['score'][1]:
            return False
    return True

def get_score_report(games):
    all_text = []
    for game in games.values():
        away_team, home_team = game['away'], game['home']
        away_score, home_score = game['score']
        text = '<%s|%s %s, %s %s with %s remaining in Q%s>' % (game['url'], away_team, 
            away_score, home_team, home_score, game['displayClock'], game['quarter'])
        if away_score + home_score == 0: # game hasn't started
            text = '<%s|%s @ %s at %s>\n%s Watchability' % (game['url'], away_team, home_team, 
                game['time'], game['Watchability'])
        elif game['quarter'] >= 4 and game['clock'] <= CLOCK_ZERO and away_score != home_score: # game completed
            text = '%s %s, %s %s' % (away_team, away_score, home_team, home_score)
        all_text.append(text)
    score_report = '\n\n'.join(all_text)
    return score_report
