from bs4 import BeautifulSoup
from slack import WebClient
import watchability
import requests

def set_games():
    ## find good streaming site

    # response = requests.get('http://nbastreams.xyz')
    # soup = BeautifulSoup(response.text, 'html.parser')
    # content = soup.find_all('a', class_ = 'btn btn-default btn-lg btn-block')
    # games = {}
    # for a_tag in content:
    #     url = a_tag['href']
    #     time = a_tag.find('p').text.split(' - ')[1]
    #     teams = a_tag.find('h4').text.strip().split(' vs ')
    #     if len(teams) < 2:
    #         teams = a_tag.find('h4').text.strip().split(' at ')
    #     away = teams[0].split()[-1]
    #     home = teams[1].split()[-1]
    #     games[(away, home)] = {'url':url, 'time':time}
    # return games

def update_games(games):
    ## bring in count, outs, men on base

    espn_api = 'http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard'
    response = requests.get(espn_api)
    data = response.json()
    for event in data['events']:
        home, away = event['competitions'][0]['competitors']
        away_team = away['team']['name']
        home_team = home['team']['name']
        games[(away_team, home_team)] = {
            'score':(int(away['score']), int(home['score'])),
            'inning':event['status']['period'],
            'clock':event['status']['clock'],
            'displayClock':event['status']['displayClock']
        }
    return games

def check_for_new_alerts(games, alerted):
    ## base off of score, inning, # of outs, # of men on base

    # new_alerts = set()
    # for teams, game in games.items():
    #     if teams not in alerted and game['quarter'] == 4 and game['clock'] > 0 and game['clock'] <= 300:
    #         differential = abs(game['score'][0] - game['score'][1])
    #         if differential <= 5:
    #             new_alerts.add(teams)
    # return new_alerts

def get_daily_report(games):
    ## base off of 538 predictions page

    # ratings = watchability.get_team_ratings()
    # watchability_dict = watchability.get_watchability(ratings)
    # for game in games:
    #     games[game].update(watchability_dict[game])
    # all_text = []
    # for teams, game in games.items():
    #     text = '%s @ %s at %s\nWatch at: %s\n%s Watchability' % (teams[0],
    #             teams[1], game['time'], game['url'], game['Watchability'])
    #     all_text.append(text)
    # daily_report = '\n\n'.join(all_text)
    # return daily_report