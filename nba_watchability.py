from bs4 import BeautifulSoup
import requests
import nba_elo

def get_team_ratings():
    ratings = nba_elo.get_output()
    return ratings

def has_favorite_teams(teams):
    # TODO: Replace with dynamic preferences per user.
    FAV_TEAMS = ['Knicks']
    # Finds intersection between favorite teams and teams in the matchup.
    return set(teams) & set(FAV_TEAMS)

def get_watchability(ratings):
    watchability_dict = {}
    espn_api = 'http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
    response = requests.get(espn_api)
    data = response.json()
    for event in data['events']:
        home, away = event['competitions'][0]['competitors']
        away_team = away['team']['displayName'].split()[-1]
        home_team = home['team']['displayName'].split()[-1]
        away_rating = ratings[away_team]
        home_rating = ratings[home_team]
        total_rating = away_rating + home_rating
        net_rating = abs(home_rating - away_rating)
        watchability = 'Medium'
        if has_favorite_teams([home_team, away_team]):
            watchability = 'High'
        elif total_rating < 3000 or net_rating > 200:
            watchability = 'Low'
        elif total_rating > 3200:
            watchability = 'High'
        watchability_dict[(away_team, home_team)] = {
            'Away Rating' : away_rating,
            'Home Rating' : home_rating,
            'Watchability' : watchability
        }

    return watchability_dict
