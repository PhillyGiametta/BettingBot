import os
import datetime
import requests
from dotenv import load_dotenv
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# Obtain the API key from the environment variable
API_KEY = os.getenv("")

# Discord bot token and channel ID from environment variables
DISCORD_TOKEN = os.getenv("")
DISCORD_CHANNEL_ID = os.getenv("")

# Sport keys
SPORTS = ['basketball_nba', 'baseball_mlb', 'soccer_epl', 'soccer_spain_la_liga', 'soccer_usa_mls']
# Bookmaker regions
REGIONS = 'us'
BOOKMAKERS = "pinnacle,draftkings,fanduel,betmgm,pointsbetus,betrivers,williamhill_us,betonlineag,wynnbet"
# Odds markets
MARKETS = 'h2h'
# Odds format
ODDS_FORMAT = 'american'
# Date format
DATE_FORMAT = 'iso'

def odds_api_call(api_key, sport, bookmakers=BOOKMAKERS, markets=MARKETS, oddsFormat=ODDS_FORMAT, dateFormat=DATE_FORMAT):
    current_datetime = datetime.datetime.now()
    iso_current_datetime = current_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

    odds_response = requests.get(f'https://api.the-odds-api.com/v4/sports/{sport}/odds', params={
        'api_key': api_key,
        'bookmakers': bookmakers,
        'markets': markets,
        'oddsFormat': oddsFormat,
        'dateFormat': dateFormat,
        'commenceTimeFrom': iso_current_datetime
    })

    if odds_response.status_code != 200:
        print(f'Failed to get odds: status_code {odds_response.status_code}, response body {odds_response.text}')
        return None
    else:
        odds_json = odds_response.json()
        print('Number of events:', len(odds_json))
        print('Remaining requests', odds_response.headers.get('x-requests-remaining'))
        print('Used requests', odds_response.headers.get('x-requests-used'))
        return odds_json

def american_to_prob(price):
    if price < 0:
        risk = abs(price)
        return_num = risk + 100
    else:
        risk = 100
        return_num = risk + price
    return risk / return_num

def get_ev_games(odds_json):
    df = pd.json_normalize(odds_json)

    pinnacle_probs_list = []
    remove_games_list = []
    pinnacle_odds_list = []

    for i in range(len(df)):
        maker_list = df["bookmakers"].iloc[i]
        pinnacle_checker = False
        for maker in maker_list:
            if maker["key"] == "pinnacle":
                pinnacle_checker = True
                if len(maker["markets"][0]["outcomes"]) == 2:
                    pinnacle1 = maker["markets"][0]["outcomes"][0]["price"]
                    pinnacle2 = maker["markets"][0]["outcomes"][1]["price"]
                    team1 = maker["markets"][0]["outcomes"][0]["name"]
                    team2 = maker["markets"][0]["outcomes"][1]["name"]
                    pinnacle1_prob = american_to_prob(pinnacle1)
                    pinnacle2_prob = american_to_prob(pinnacle2)

                    pinnacle1_prob_actual = pinnacle1_prob / (pinnacle1_prob + pinnacle2_prob)
                    pinnacle2_prob_actual = pinnacle2_prob / (pinnacle1_prob + pinnacle2_prob)

                    pinnacle_probs_list.append({team1: pinnacle1_prob_actual, team2: pinnacle2_prob_actual})
                    pinnacle_odds_list.append({team1: pinnacle1, team2: pinnacle2})
                if len(maker["markets"][0]["outcomes"]) == 3:
                    pinnacle1 = maker["markets"][0]["outcomes"][0]["price"]
                    pinnacle2 = maker["markets"][0]["outcomes"][1]["price"]
                    pinnacle3 = maker["markets"][0]["outcomes"][2]["price"]
                    team1 = maker["markets"][0]["outcomes"][0]["name"]
                    team2 = maker["markets"][0]["outcomes"][1]["name"]
                    team3 = maker["markets"][0]["outcomes"][2]["name"]
                    pinnacle1_prob = american_to_prob(pinnacle1)
                    pinnacle2_prob = american_to_prob(pinnacle2)
                    pinnacle3_prob = american_to_prob(pinnacle3)

                    pinnacle1_prob_actual = pinnacle1_prob / (pinnacle1_prob + pinnacle2_prob + pinnacle3_prob)
                    pinnacle2_prob_actual = pinnacle2_prob / (pinnacle1_prob + pinnacle2_prob + pinnacle3_prob)
                    pinnacle3_prob_actual = pinnacle3_prob / (pinnacle1_prob + pinnacle2_prob + pinnacle3_prob)

                    pinnacle_probs_list.append({team1: pinnacle1_prob_actual, team2: pinnacle2_prob_actual, team3: pinnacle3_prob_actual})
                    pinnacle_odds_list.append({team1: pinnacle1, team2: pinnacle2, team3: pinnacle3})
        if not pinnacle_checker:
            remove_games_list.append(i)

    subtraction = 0
    for i in remove_games_list:
        df = df.drop(df.index[i - subtraction])
        subtraction += 1
    df.reset_index(drop=True, inplace=True)

    df["pinnacle_probs"] = pinnacle_probs_list
    df["pinnacle_odds"] = pinnacle_odds_list

    plus_ev_df = pd.DataFrame(columns=["Team Name", "Sportsbook", "Sportsbook Odds", "Pinnacle Odds", "EV"])

    for i in range(len(df)):
        maker_list = df["bookmakers"].iloc[i]
        pinnacle_dict = df["pinnacle_probs"].iloc[i]
        for maker in maker_list:
            if maker["key"] == "pinnacle":
                continue
            if len(maker["markets"][0]["outcomes"]) == 2:
                book1 = maker["markets"][0]["outcomes"][0]["price"]
                book2 = maker["markets"][0]["outcomes"][1]["price"]
                team1 = maker["markets"][0]["outcomes"][0]["name"]
                team2 = maker["markets"][0]["outcomes"][1]["name"]

                team1_actual_probs = pinnacle_dict[team1]
                team2_actual_probs = pinnacle_dict[team2]

                if book1 < 0:
                    profit1 = 100
                    loss1 = abs(book1)
                else:
                    profit1 = abs(book1)
                    loss1 = 100

                if book2 < 0:
                    profit2 = 100
                    loss2 = abs(book2)
                else:
                    profit2 = abs(book2)
                    loss2 = 100

                EV1 = (team1_actual_probs * profit1) - (1 - team1_actual_probs) * loss1
                EV2 = (team2_actual_probs * profit2) - (1 - team2_actual_probs) * loss2

                pinnacle_odds_dict = df["pinnacle_odds"].iloc[i]
                pinnacle_odds1 = pinnacle_odds_dict[team1]
                pinnacle_odds2 = pinnacle_odds_dict[team2]

                if EV1 > 0:
                    new_row = {"Team Name": team1, "Sportsbook": maker['key'], "Sportsbook Odds": book1, "Pinnacle Odds": pinnacle_odds1, "EV": EV1}
                    plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index=[0])], axis=0, ignore_index=True)

                if EV2 > 0:
                    new_row = {"Team Name": team2, "Sportsbook": maker['key'], "Sportsbook Odds": book2, "Pinnacle Odds": pinnacle_odds2, "EV": EV2}
                    plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index=[0])], axis=0, ignore_index=True)

            if len(maker["markets"][0]["outcomes"]) == 3:
                book1 = maker["markets"][0]["outcomes"][0]["price"]
                book2 = maker["markets"][0]["outcomes"][1]["price"]
                book3 = maker["markets"][0]["outcomes"][2]["price"]
                team1 = maker["markets"][0]["outcomes"][0]["name"]
                team2 = maker["markets"][0]["outcomes"][1]["name"]
                team3 = maker["markets"][0]["outcomes"][2]["name"]

                team1_actual_probs = pinnacle_dict[team1]
                team2_actual_probs = pinnacle_dict[team2]
                team3_actual_probs = pinnacle_dict[team3]

                if book1 < 0:
                    profit1 = 100
                    loss1 = abs(book1)
                else:
                    profit1 = abs(book1)
                    loss1 = 100

                if book2 < 0:
                    profit2 = 100
                    loss2 = abs(book2)
                else:
                    profit2 = abs(book2)
                    loss2 = 100

                if book3 < 0:
                    profit3 = 100
                    loss3 = abs(book3)
                else:
                    profit3 = abs(book3)
                    loss3 = 100

                EV1 = (team1_actual_probs * profit1) - (1 - team1_actual_probs) * loss1
                EV2 = (team2_actual_probs * profit2) - (1 - team2_actual_probs) * loss2
                EV3 = (team3_actual_probs * profit3) - (1 - team3_actual_probs) * loss3

                pinnacle_odds_dict = df["pinnacle_odds"].iloc[i]
                pinnacle_odds1 = pinnacle_odds_dict[team1]
                pinnacle_odds2 = pinnacle_odds_dict[team2]
                pinnacle_odds3 = pinnacle_odds_dict[team3]

                if EV1 > 0:
                    new_row = {"Team Name": team1, "Sportsbook": maker['key'], "Sportsbook Odds": book1, "Pinnacle Odds": pinnacle_odds1, "EV": EV1}
                    plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index=[0])], axis=0, ignore_index=True)

                if EV2 > 0:
                    new_row = {"Team Name": team2, "Sportsbook": maker['key'], "Sportsbook Odds": book2, "Pinnacle Odds": pinnacle_odds2, "EV": EV2}
                    plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index=[0])], axis=0, ignore_index=True)

                if EV3 > 0:
                    new_row = {"Team Name": team1 + " v " + team2 + " " + team3, "Sportsbook": maker['key'], "Sportsbook Odds": book3, "Pinnacle Odds": pinnacle_odds3, "EV": EV3}
                    plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index=[0])], axis=0, ignore_index=True)

    plus_ev_df = plus_ev_df.sort_values(by=['EV'], ascending=False)
    return plus_ev_df

def send_message_to_discord(content):
    discord_url = f"https://discord.com/api/v9/channels/{DISCORD_CHANNEL_ID}/messages"
    headers = {
        'Authorization': f'Bot {DISCORD_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        'content': content
    }
    response = requests.post(discord_url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Failed to send message to Discord: {response.status_code}, response: {response.text}")
    else:
        print("Message sent successfully")

def run(event, lambda_context):
    for sport in SPORTS:
        print(sport)
        odds_json = odds_api_call(api_key=API_KEY, sport=sport)
        if odds_json:
            message_content = get_ev_games(odds_json).to_markdown()
            send_message_to_discord(message_content)
