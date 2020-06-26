from bs4 import BeautifulSoup
import requests

def get_team_ratings():
    url = 'https://projects.fivethirtyeight.com/2020-nba-predictions/'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.find(id='standings-table').find('tbody').find_all('tr')

    ratings = {}
    for tr in content:
        rating = int(tr.find('td', class_='num elo carmelo-current').text)
        team = tr.find('td', class_='team').find('a').text.split()[-1]
        ratings[team] = rating
    return ratings

def get_watchability(ratings):
    url = 'https://projects.fivethirtyeight.com/2020-nba-predictions/games/'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.find(id='upcoming-days').find_all('div')[0].find_all('tbody')

    watchability_dict = {}
    for tbody in content:
        s1, s2 = tbody.find_all(class_='td number spread')
        spread = max((s1.text, s2.text), key=lambda s: len(s))
        spread = float(spread[2:]) if spread != ' PK' else 0.0
        away = tbody.find_all('tr')[1].find_all('td')[2].text.split()[-1]
        home = tbody.find_all('tr')[2].find_all('td')[2].text.split()[-1]
        away_rating = ratings[away]
        home_rating = ratings[home]
        watchability = 'Medium'
        if away == 'Knicks' or home == 'Knicks': ## knicks factor
            watchability = 'High'
        elif home_rating + away_rating < 3000 or spread > 5:
            watchability = 'Low'
        elif home_rating + away_rating > 3200:
            watchability = 'High'
        watchability_dict[(away, home)] = {
            'Spread' : spread,
            'Away Rating' : away_rating,
            'Home Rating' : home_rating,
            'Watchability' : watchability
        }

    return watchability_dict