import logging
from datetime import datetime as dt
import nba_watchability
import requests

SCOREBOARD_URL = 'http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
STREAM_BASE_URL = 'https://crackstreams.mx/stream'
# National broadcasters (ESPN's names) -> streaming app; other games fall back to STREAM_BASE_URL
NATIONAL_STREAMS = {
    'ESPN': ('ESPN', 'https://www.espn.com/watch/'),
    'ABC': ('ESPN', 'https://www.espn.com/watch/'),
    'NBC': ('Peacock', 'https://www.peacocktv.com/sports/nba'),
    'NBCSN': ('Peacock', 'https://www.peacocktv.com/sports/nba'),
    'Peacock': ('Peacock', 'https://www.peacocktv.com/sports/nba'),
    'Prime Video': ('Prime Video', 'https://www.primevideo.com/'),
}

def get_national_stream(event):
    for broadcast in event['competitions'][0].get('broadcasts', []):
        if broadcast.get('market') != 'national':
            continue
        for name in broadcast.get('names', []):
            if name in NATIONAL_STREAMS:
                return NATIONAL_STREAMS[name]
    return None, None

def get_service_label(game):
    return ' (%s)' % game['service'] if game['service'] else ''

def get_scoreboard(slate_date):
    # request the date explicitly: until late morning the default scoreboard still shows last night's games
    response = requests.get(SCOREBOARD_URL, params={'dates': slate_date.strftime('%Y%m%d')}, timeout=10)
    response.raise_for_status()
    return response.json()

def set_game_urls(games):
    for game in games.values():
        if game['national_url']:
            game['url'] = game['national_url']
            continue
        away_full = game['away_full']
        home_full = game['home_full']
        url1 = '%s/%s-vs-%s' % (STREAM_BASE_URL, away_full, home_full)
        url2 = '%s/%s-vs-%s' % (STREAM_BASE_URL, home_full, away_full)
        try:
            url = url2 if '404 Not Found - CrackStreamsms' in requests.get(url1, timeout=5).text else url1
        except Exception as e:
            logging.warning('Could not fetch stream URL for %s vs %s: %s', away_full, home_full, e)
            url = '#'
        game['url'] = url

def set_games(slate_date):
    data = get_scoreboard(slate_date)
    games = {}
    for event in data['events']:
        home, away = event['competitions'][0]['competitors']
        away_team, home_team = nba_watchability.get_team_names(event)
        service, national_url = get_national_stream(event)
        start = dt.fromisoformat(event['date']).astimezone() # ESPN dates are UTC, e.g. 2026-10-20T23:00Z
        # keyed by ESPN event id: stable across polls, unlike team names
        games[event['id']] = {
            'away': away_team,
            'home': home_team,
            'start': start.replace(tzinfo=None),
            'time': start.strftime('%-I:%M %p %Z'),
            'state': event['status']['type']['state'],
            'away_full': away['team']['displayName'].replace(' ', '-').replace('LA', 'Los-Angeles'),
            'home_full': home['team']['displayName'].replace(' ', '-').replace('LA', 'Los-Angeles'),
            'score': (0, 0),
            'quarter': 0,
            'clock': 9999.0,
            'displayClock': '',
            'service': service,
            'national_url': national_url,
        }
    set_game_urls(games)
    return games

def update_games(games, slate_date):
    data = get_scoreboard(slate_date)
    for event in data['events']:
        if event['id'] not in games:
            logging.warning('Skipping unknown game %s (%s)', event['id'], event.get('name'))
            continue
        home, away = event['competitions'][0]['competitors']
        games[event['id']].update({
            'score':(int(away['score']), int(home['score'])),
            'quarter':event['status']['period'],
            'clock':event['status']['clock'],
            'displayClock':event['status']['displayClock'],
            'state':event['status']['type']['state'], # 'post' covers final, postponed, and canceled
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
    matchups = [(game['away'], game['home']) for game in games.values()]
    watchability_dict = nba_watchability.get_watchability(ratings, matchups)
    default_watchability = {'Watchability': 'Medium', 'Away Rating': 0, 'Home Rating': 0}
    for game in games.values():
        game.update(watchability_dict.get((game['away'], game['home']), default_watchability))
    all_text = []
    for game in games.values():
        text = '<%s|%s @ %s at %s>%s\n%s Watchability' % (game['url'], game['away'], game['home'], 
            game['time'], get_service_label(game), game['Watchability'])
        all_text.append(text)
    daily_report = '\n\n'.join(all_text)
    return daily_report

def send_alerts(client, games, alerted, slate_date):
    games = update_games(games, slate_date)
    new_alerts = check_for_new_alerts(games, alerted)
    for timeframe, game_ids in new_alerts.items():
        for game_id in game_ids:
            game = games[game_id]
            away_team, home_team = game['away'], game['home']
            away_score, home_score = game['score']
            text = '<%s|%s %s, %s %s. %s remaining>%s' % (game['url'], away_team, away_score, 
            	home_team, home_score, game['displayClock'], get_service_label(game))
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
    return min(game['start'] for game in games.values())

def is_completed(games):
    return all(game['state'] == 'post' for game in games.values())

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
        elif game['state'] == 'post': # game completed
            text = '%s %s, %s %s' % (away_team, away_score, home_team, home_score)
        all_text.append(text)
    score_report = '\n\n'.join(all_text)
    return score_report
