import logging
from nba_api.stats.library.parameters import Season
from nba_api.stats.static import teams
import nba_api.stats.endpoints as endpoints
import pandas as pd

# FiveThirtyEight carries 75% of a team's end-of-season rating into the next season
# and reverts the rest toward the league mean of 1505
SEASON_CARRYOVER = 0.75
MEAN_ELO = 1505

def get_games(headers, season):
    leaguegamelog = endpoints.leaguegamelog.LeagueGameLog(season=season, headers=headers)
    df_games = leaguegamelog.get_data_frames()[0]
    return df_games

def get_updated_elo_ratings(r_a, r_h, point_differential):
    k = 20
    
    home_advantage = 50
    r_h_adj = r_h + home_advantage # adjust for home court advantage
    r_a_adj = r_a - home_advantage # adjust for home court advantage

    elo_diff = r_h_adj - r_a_adj
    if point_differential < 0 and elo_diff >= 0: # Underdog (away team) won
        elo_diff *= -1 # Negative elo_diff indicates underdog win

    mov = abs(point_differential)
    multiplier = (mov + 3) ** 0.8 / (7.5 + 0.006 * elo_diff)
    
    e_a = 1.0 / (1 + 10 ** ((r_h_adj - r_a_adj) / 400.0))
    e_h = 1.0 / (1 + 10 ** ((r_a_adj - r_h_adj) / 400.0))
    s_a = 1 if point_differential < 0 else 0
    s_h = 1 if point_differential > 0 else 0
    r_a_new = r_a + k * multiplier * (s_a - e_a)
    r_h_new = r_h + k * multiplier * (s_h - e_h)
    return r_a_new, r_h_new

def get_previous_season(season):
    start_year = int(season[:4]) - 1 # '2026-27' -> '2025-26'
    return '%d-%s' % (start_year, str(start_year + 1)[2:])

def apply_games(elos, df_games):
    for _, game in df_games.iterrows():
        if 'vs.' in game['MATCHUP']:
            continue
        away_team, home_team = game['MATCHUP'].split(' @ ')
        point_differential = game['PLUS_MINUS'] * -1
        elos[away_team], elos[home_team] = get_updated_elo_ratings(elos[away_team], elos[home_team], point_differential)

def get_team_elos():
    headers = {
        "Host": "stats.nba.com",
        "Connection": "keep-alive",
        "Accept": "application/json, text/plain, /",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    df_teams = pd.DataFrame(teams.get_teams())
    elos = {team: 1500 for team in df_teams['abbreviation']}
    season = Season.default
    try:
        previous_elos = dict(elos)
        apply_games(previous_elos, get_games(headers, get_previous_season(season)))
        elos = {team: SEASON_CARRYOVER * rating + (1 - SEASON_CARRYOVER) * MEAN_ELO
                for team, rating in previous_elos.items()}
    except Exception as e:
        logging.warning('Could not carry over last season\'s ratings; starting from 1500: %s', e)
    apply_games(elos, get_games(headers, season))
    return elos

def get_output():
    elos = get_team_elos()
    df_teams = pd.DataFrame(teams.get_teams())
    df_teams['rating'] = df_teams['abbreviation'].map(elos).round()
    output = {row['nickname']: row['rating'] for _, row in df_teams.iterrows()}
    return output