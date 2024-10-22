from nba_api.stats.static import teams
import nba_api.stats.endpoints as endpoints
import pandas as pd

def get_games(season):
    leaguegamelog = endpoints.leaguegamelog.LeagueGameLog(season=season, player_or_team_abbreviation='T')
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
    multiplier = (mov+3)**0.8 / (7.5 + 0.006 * elo_diff)
    
    e_a = 1.0 / (1 + 10**((r_h_adj - r_a_adj) / 400.0))
    e_h = 1.0 / (1 + 10**((r_a_adj - r_h_adj) / 400.0))
    s_a = 1 if point_differential < 0 else 0
    s_h = 1 if point_differential > 0 else 0
    r_a_new = r_a + k * multiplier * (s_a - e_a)
    r_h_new = r_h + k * multiplier * (s_h - e_h)
    return r_a_new, r_h_new

def get_team_elos(season):
    df_teams = pd.DataFrame(teams.get_teams())
    df_games = get_games(season)
    elos = {team: 1500 for team in df_teams['abbreviation']}
    for date, group in df_games.groupby('GAME_DATE'):
        for game_id, match in group.groupby('GAME_ID'):
            for _, game in match.iterrows():
                if 'vs.' in game['MATCHUP']:
                    continue
                away_team, home_team = game['MATCHUP'].split(' @ ')
                point_differential = game['PLUS_MINUS'] * -1                
                elos[away_team], elos[home_team] = get_updated_elo_ratings(elos[away_team], elos[home_team], point_differential)
    return elos

def get_output():
    season = '2024-25'
    elos = get_team_elos(season)
    df_teams = pd.DataFrame(teams.get_teams())
    df_teams['rating'] = df_teams['abbreviation'].map(elos).round()
    output = {row['nickname']: row['rating'] for _, row in df_teams.iterrows()}
    return output