'''
pip install discord-py-interactions
pip install discord-py-slash-command

'''

import asyncio
import discord
import os
from dotenv import load_dotenv, find_dotenv
from discord import app_commands
from discord.utils import get
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from discord.ext import commands
import sqlite3
import random
from operator import itemgetter
import itertools
import numpy as np
# from discord_slash import SlashCommand, SlashContext
# from discord_slash.utils.manage_commands import create_choice, create_option
# import logging
# import gspread
# from oauth2client.service_account import ServiceAccountCredentials
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError

load_dotenv(find_dotenv())
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

TOKEN = os.getenv('BOT_TOKEN')#Gets the bot's password token from the .env file and sets it to TOKEN.
GUILD = os.getenv('GUILD_ID')#Gets the server's id from the .env file and sets it to GUILD.
SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')#Gets the Google Sheets ID from the .env file and sets it to SHEETS_ID.
SHEETS_NAME = os.getenv('GOOGLE_SHEETS_NAME')#Gets the google sheets name from the .env and sets it to SHEETS_NAME
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']#Allows the app to read and write to the google sheet.
SERVICE_ACCOUNT_FILE = 'token.json' #Location of Google Sheets credential file

# Create credentials object
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

@client.event
async def on_ready():
    check_database()
    await tree.sync(guild=discord.Object(GUILD))
    print(f'Logged in as {client.user}')

"""#Logger to catch discord disconects and ignores them.
class GatewayEventFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__('discord.gateway')
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info is not None and isinstance(record.exc_info[1], discord.ConnectionClosed):
            return False
        return True"""

#region CLASSES
#Player class.
class Player:
    def __init__(self, tier, username, discord_id, top_priority, jungle_priority, mid_priority, bot_priority, support_priority):
        self.tier = tier
        self.username = username
        self.discord_id = discord_id
        self.top_priority = top_priority
        self.jungle_priority = jungle_priority
        self.mid_priority = mid_priority
        self.bot_priority = bot_priority
        self.support_priority = support_priority

    def __str__(self):
        return f"Player: {self.username} (Tier {self.tier}), Top: {self.top_priority}, Jungle: {self.jungle_priority}, Mid: {self.mid_priority}, Bot: {self.bot_priority}, Support: {self.support_priority}"

    def set_roles(self, top_priority, jungle_priority, mid_priority, bot_priority, support_priority):
        self.top_priority = top_priority
        self.jungle_priority = jungle_priority
        self.mid_priority = mid_priority
        self.bot_priority = bot_priority
        self.support_priority = support_priority

#Team class.
class Team:
    def __init__(self, top_laner, jungle, mid_laner, bot_laner, support):
        self.top_laner = top_laner
        self.jungle = jungle
        self.mid_laner = mid_laner
        self.bot_laner = bot_laner
        self.support = support

    def __str__(self):
        return f"Top Laner: {self.top_laner.username} priority: {self.top_laner.top_priority} (Tier {self.top_laner.tier})\nJungle: {self.jungle.username} priority:{self.jungle.jungle_priority} \
              (Tier {self.jungle.tier})\nMid Laner: {self.mid_laner.username} priority: {self.mid_laner.mid_priority} (Tier {self.mid_laner.tier})\nBot Laner: {self.bot_laner.username} \
                  priority: {self.bot_laner.bot_priority} (Tier {self.bot_laner.tier})\nSupport: {self.support.username} priority: {self.support.support_priority} (Tier {self.support.tier})"

#Dropdown class for rendering the player role preference dropdown options
class Dropdown(discord.ui.Select):
    def __init__(self, position):
        options = [
            discord.SelectOption(label=f'{position} - 1', description=f'Highest priority'),
            discord.SelectOption(label=f'{position} - 2', description=f'Higher priority'),
            discord.SelectOption(label=f'{position} - 3', description=f'Medium priority'),
            discord.SelectOption(label=f'{position} - 4', description=f'Low Priority'),
            discord.SelectOption(label=f'{position} - 5', description=f'Absolutely not'),
        ]
        super().__init__(placeholder=f'{position} preference..', options=options)

    async def callback(self, interaction: discord.Interaction):
        save_preference(interaction, self.values[0])
        await interaction.response.send_message(f'Updated {self.values[0]} for {self.placeholder}', ephemeral=True)

#Button to set preferences to fill - embed did not have room so is unused currently
class FillButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Set to Fill", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        save_preference(interaction, "Fill - 44444")
        await interaction.response.send_message(f'Set preference to "Fill"', ephemeral=True)

##Help view - provide instructions, commands, and button choices
## Add button to launch preferences, launch fill, and decribe functions, etc
# class HelpView(discord.ui.view):
#     def __init__(self):
#         super().__init__()
#         return

#Dropdown view for rendering all dropdowns for player role preferences
class DropdownView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(Dropdown("Top"))
        self.add_item(Dropdown("Jng"))
        self.add_item(Dropdown("Mid"))
        self.add_item(Dropdown("ADC"))
        self.add_item(Dropdown("Sup"))
        # self.add_item(FillButton()) 

#Checkin button class for checking in to tournaments.
class CheckinButtons(discord.ui.View):
    def __init__(self, *, timeout):
        super().__init__(timeout = timeout)

    """
    This button is a green button that is called check in
    When this button is pulled up, it will show the text "Check-In"

    The following output when clicking the button is to be expected:
    If the user already has the player role, it means that they are already checked in.
    If the user doesn't have the player role, it will give them the player role. 
    """

    @discord.ui.button(
            label = "Check-In",
            style = discord.ButtonStyle.green)
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):

        player = get(interaction.guild.roles, name = 'Player')
        member = interaction.user

        riotID = register_player(interaction)

        if player in member.roles:
            await interaction.response.edit_message(view = self)
            await interaction.followup.send('You have already checked in.', ephemeral=True)
            return "Is already checked in"
        await member.add_roles(player)
        await interaction.response.edit_message(view = self)
        await interaction.followup.send(f'You have checked in with Riot ID "{riotID}"!  Be sure to check your /roleselect and update your /riotID if needed.', ephemeral = True)
        # await roleselect(interaction)
        return "Checked in"        

    """
    This button is the leave button. It is used for if the player checked in but has to leave
    The following output is to be expected:

    If the user has the player role, it will remove it and tell the player that it has been removed
    If the user does not have the player role, it will tell them to check in first.
    """
    @discord.ui.button(
            label = "Leave",
            style = discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):

        player = get(interaction.guild.roles, name = 'Player')
        member = interaction.user

        if player in member.roles:
            await member.remove_roles(player)
            await interaction.response.edit_message(view = self)
            await interaction.followup.send('Sorry to see you go.', ephemeral = True)
            return "Role Removed"
        await interaction.response.edit_message(view = self)
        await interaction.followup.send('You have not checked in. Please checkin first', ephemeral = True)
        return "Did not check in yet"

#Volunteer button class
class volunteerButtons(discord.ui.View):
    def __init__(self, *, timeout = 900):
        super().__init__(timeout = timeout)
    """
    This button is a green button that is called check in
    When this button is pulled up, it will show the text "Volunteer"

    The following output when clicking the button is to be expected:
    If the user already has the volunteer role, it means that they are already volunteered.
    If the user doesn't have the volunteer role, it will give them the volunteer role. 
    """
    @discord.ui.button(
            label = "Volunteer",
            style = discord.ButtonStyle.green)
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):

        player = get(interaction.guild.roles, name = 'Player')
        volunteer = get(interaction.guild.roles, name = 'Volunteer')
        member = interaction.user

        if player in member.roles:
            await member.remove_roles(player)
        if volunteer in member.roles:
            await interaction.response.edit_message(view = self)
            await interaction.followup.send('You have already volunteered to sit out, if you wish to rejoin click rejoin.', ephemeral=True)
            return "Is already checked in"
        await member.add_roles(volunteer)
        await interaction.response.edit_message(view = self)
        await interaction.followup.send('You have volunteered to sit out!', ephemeral = True)
        return "Checked in"        

    """
    This button is the leave button. It is used for if the player who has volunteer wants to rejoin
    The following output is to be expected:

    If the user has the player role, it will remove it and tell the player that it has been removed
    If the user does not have the volunteer role, it will tell them to volunteer first.
    """
    @discord.ui.button(
            label = "Rejoin",
            style = discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        player = get(interaction.guild.roles, name = 'Player')
        volunteer = get(interaction.guild.roles, name = 'Volunteer')
        member = interaction.user

        if volunteer in member.roles:
            await member.remove_roles(volunteer)
            await member.add_roles(player)
            await interaction.response.edit_message(view = self)
            await interaction.followup.send('Welcome back in!', ephemeral = True)
            return "Role Removed"
        await interaction.response.edit_message(view = self)
        await interaction.followup.send('You have not volunteered to sit out, please volunteer to sit out first.', ephemeral = True)
        return "Did not check in yet"

#endregion CLASSES


#region METHODS

#Method to return string of preferences for the /preferences embed
def get_preferences(interaction: discord.Interaction):
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        pref = "No existing preferences, use the dropdowns to select:"

        query = 'SELECT preferences FROM Player WHERE DiscordID = ?'
        args = (interaction.user.id,)
        cur.execute(query, args)
        result = cur.fetchone()

        if result[0] != 0:
            pref = f"Current preferences - Top: {result[0][0]}, Jng: {result[0][1]}, Mid: {result[0][2]}, ADC: {result[0][3]}, Sup: {result[0][4]}" 

        return pref
    except sqlite3.Error as e:
        print (f'Database error occurred getting preferences: {e}')
        return e

    finally:
        cur.close()
        dbconn.close()    
    
#Method to save player's preference selection
def save_preference(interaction: discord.Interaction, value: str):
    position = value.split(" - ")[0]
    setpref = value.split(" - ")[1]
    member = interaction.user

    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        query = 'SELECT preferences FROM player WHERE discordID = ?'
        args = (member.id,)
        cur.execute(query, args)
        result = cur.fetchone()

        match position:
            case "Fill":
                newpref = "11111"
            case "Top":
                newpref = setpref + result[0][1] + result[0][2] + result[0][3] + result[0][4]
            case "Jng":
                newpref = result[0][0] + setpref + result[0][2] + result[0][3] + result[0][4]
            case "Mid":
                newpref = result[0][0] + result[0][1] + setpref + result[0][3] + result[0][4]
            case "ADC":
                newpref = result[0][0] + result[0][1] + result[0][2] + setpref + result[0][4] 
            case "Sup":
                newpref = result[0][0] + result[0][1] + result[0][2] + result[0][3] + setpref

        query = 'UPDATE Player SET Preferences = ? WHERE discordID = ?'
        args = (newpref, member.id,)        
        cur.execute(query, args)
        dbconn.commit()

    except sqlite3.Error as e:
        print(f"Database error occurred updating preferences: {e}")

    finally:
        cur.close()
        dbconn.close()

#Method to check if player exists in the database and adds them if not
def register_player(interaction: discord.Interaction):
    member = interaction.user
    
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        query = 'SELECT EXISTS(SELECT discordName FROM player WHERE discordID = ?)'
        args = (member.id,)
        cur.execute(query, args)
        data = cur.fetchone()

        if data[0] == 0:
            query = "INSERT INTO Player (discordID, discordName, riotID, lolRank, preferences, toxicity) VALUES (?, ?, '', 'Bronze', '11111', 0)"
            args = (member.id, member.name,)
            cur.execute(query, args)
            dbconn.commit()

            return "n/a"
        else:
            query = 'SELECT discordName, riotID FROM Player WHERE discordID = ?'
            args = (member.id,)
            cur.execute(query, args)
            result = cur.fetchone()

            if member.name != result[0]:
                query = "UPDATE Player SET discordName = ? WHERE discordID = ?"
                args = (member.name, member.id,)
                cur.execute(query, args)
                dbconn.commit()                

            return str(result[1]).strip()

    except sqlite3.Error as e:
        print(f"Database error occurred registering player: {e}")

    finally:
        cur.close()
        dbconn.close()

#Method to create the database and objects if it is not found
def check_database():
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS Player (
            discordID bigint PRIMARY KEY     	-- Unique Discord identifier for the player, will serve as PK
            , discordName nvarchar(64)			-- Player's Discord name
            , riotID nvarchar(64)				-- Player's LOL name
            , lolRank varchar(32)				-- Player's LOL rank
            , preferences varchar(512)			-- Player's encoded lane preferences (1H-5L) in order of Top, Jungle, Mid, ADC, and Support
            , toxicity int                      -- Player's toxicity score
            , tieroverride int                  -- Used by admins to override player's tier score, 0 uses calculated value
            );""")
        
        cur.execute("""CREATE TABLE IF NOT EXISTS Games (
            gameID INTEGER PRIMARY KEY AUTOINCREMENT	    -- Unique ID to identify the game
            , gameDate date						-- Date of the game
            , gameNumber tinyint				-- Game number (1, 2, 3)	
            , gameLobby tinyint					-- Game Lobby (1, 2, 3) per 10 players
            , gameWinner varchar(4)				-- Team that won this game (Blue/Red)
            , isComplete bit                    -- Used to track incomplete games
            );""")

        cur.execute("""CREATE TABLE IF NOT EXISTS GameDetail (
            gameID int NOT NULL			-- Game ID joining back to the Games table
            , discordID bigint NOT NULL	-- Player ID joining back to the Player table
            , teamName varchar(32)		-- Team of the Player in this game ('Red', 'Blue', 'Participation')
            , gamePosition char(3)		-- Position played in this game (Top, Jng, Mid, ADC, Sup)
            , MVP bit					-- 0 = no MVP, 1 = MVP
            , FOREIGN KEY (gameID) REFERENCES Games (gameID)
            , FOREIGN KEY (discordID) REFERENCES Player (discordID)
            );""")
        
        cur.execute("""CREATE VIEW IF NOT EXISTS vw_Points AS
            WITH totals AS (
            SELECT p.discordID 
                , COUNT(teamName) AS Participation
                , SUM(CASE WHEN teamName = gameWinner THEN 1 ELSE 0 END) Wins
                , SUM(CASE WHEN MVP = 1 THEN 1 ELSE 0 END) MVPs
                , SUM(CASE WHEN teamName != 'Participation' THEN 1 ELSE 0 END) GamesPlayed
            FROM Player p
            INNER JOIN GameDetail gd ON gd.discordID = p.discordID
            INNER JOIN Games g ON g.gameID = gd.gameID
            GROUP BY p.discordID)

            SELECT t.discordID, p.discordName, riotID, Participation, Wins, MVPs, toxicity, GamesPlayed
                , CASE WHEN Wins = 0 OR GamesPlayed = 0 THEN 0 ELSE CAST(Wins AS float) / CAST(GamesPlayed AS float) END WinRatio
                , (Participation + Wins + MVPs - Toxicity + GamesPlayed) TotalPoints
            FROM totals t
            INNER JOIN Player p ON p.discordID = t.discordID""")        

        print ("Database is configured")
    except sqlite3.Error as e:
        print(f"Terminating due to database initialization error: {e}")
        exit()    

    finally:
        cur.close()
        dbconn.close()

#Method to add one toxicity point to the player
def update_toxicity(interaction, discord_username):
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        found_user = False

        query = 'SELECT EXISTS(SELECT discordName FROM player WHERE discordName = ?)'
        args = (discord_username,)
        cur.execute(query, args)
        data = cur.fetchone()

        if data[0] != 0:
            found_user = True
            query = 'UPDATE Player SET toxicity = toxicity + 1 WHERE discordName = ?'
            args = (discord_username,)
            cur.execute(query, args)
            dbconn.commit()         

        return found_user
    except sqlite3.Error as e:
        print (f'Database error occurred updating toxicity: {e}')
        return e

    finally:
        cur.close()
        dbconn.close()
    ## This was a new method to use Google sheets, requires discord_username to be passed
    # try:
    #     service = build('sheets', 'v4', credentials=creds)
    #     range_name = 'A1:J100'
    #     result = service.spreadsheets().values().get(spreadsheetId=SHEETS_ID, range=range_name).execute()
    #     values = result.get('values', [])
    #     found_user = False
    #     for i, row in enumerate(values, start = 1):
    #         if discord_username.lower() == row[0].lower() or discord_username.lower() == row[1].lower() :
    #             newvalue = [[int(row[5]) + 1]]
    #             body = {'range': 'Points!F' + str(i), 'values': newvalue}                
    #             update = service.spreadsheets().values().update(
    #                 spreadsheetId=SHEETS_ID, range='Points!F' + str(i),
    #                 valueInputOption='RAW', body=body).execute()
    #             found_user = True
    #             print('{0} cells updated.'.format(update.get('updatedCells')))                
    #     return found_user   

    # except HttpError as e:
    #     print(f'An error occured: {e}')
    #     return e
    
    ## This is the old/original method for Google sheets
    # gs = gspread.oauth()
    # range_name = 'A1:J100'
    # sh = gs.open(SHEETS_NAME)
    # try:
    #     values = sh.sheet1.get_values(range_name)
    #     found_user = False
    #     for i, row in enumerate(values, start = 1):
    #         if discord_username.lower() == row[0].lower():
    #             user_toxicity = int(row[5])
    #             sh.sheet1.update_cell(i, 6, user_toxicity + 1)
    #             found_user = True
    #     return found_user   
    # except HttpError as e:
    #     (f'An error occured: {e}')
    #     return e

#Method to update Riot ID
def update_riotid(interaction: discord.Interaction, id):
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        query = f"UPDATE Player SET riotID = ? WHERE discordID = ?"
        args = (id, interaction.user.id)
        cur.execute(query, args)
        dbconn.commit()
            
    except sqlite3.Error as e:
        print (f'Database error occurred updating Riot ID: {e}')
        return e

    finally:
        cur.close()
        dbconn.close()     



# Method to assign roles to players based on their preferred priority
def assign_roles(players):
    roles = ['top', 'jungle', 'mid', 'bot', 'support']
    priority_mapping = {1: [], 2: [], 3: [], 4: [], 5: []}

    for player in players:
        for idx, priority in enumerate([player.top_priority, player.jungle_priority, player.mid_priority, player.bot_priority, player.support_priority]):
            priority_mapping[int(priority)].append((player, roles[idx]))
    
    role_assignments = {}
    assigned_players = set()
    
    for priority in sorted(priority_mapping.keys()):
        for player, role in priority_mapping[priority]:
            if role not in role_assignments and player not in assigned_players:
                role_assignments[role] = player
                assigned_players.add(player)
    
    return role_assignments

# Method to create teams by sorting players by tier and then assigning roles
def create_teams(players):
    players.sort(key=lambda x: x.tier)
    team_size = len(players) // 2

    red_team_players = players[:team_size]
    blue_team_players = players[team_size:]

    red_team_roles = assign_roles(red_team_players)
    blue_team_roles = assign_roles(blue_team_players)

    red_team = Team(
        top_laner=red_team_roles['top'],
        jungle=red_team_roles['jungle'],
        mid_laner=red_team_roles['mid'],
        bot_laner=red_team_roles['bot'],
        support=red_team_roles['support']
    )

    blue_team = Team(
        top_laner=blue_team_roles['top'],
        jungle=blue_team_roles['jungle'],
        mid_laner=blue_team_roles['mid'],
        bot_laner=blue_team_roles['bot'],
        support=blue_team_roles['support']
    )

    return red_team, blue_team

# Method that validates players are within 1 tier of each other and returns true or false
def validate_team_matchup(red_team, blue_team, degree):
    roles = ['top_laner', 'jungle', 'mid_laner', 'bot_laner', 'support']
    for role in roles:
        red_player = getattr(red_team, role)
        blue_player = getattr(blue_team, role)
        if abs(red_player.tier - blue_player.tier) > degree:
            return False
    return True

# Method to create and return a balanced team
def find_balanced_teams(players, degree):
    possible_combinations = itertools.combinations(players, len(players) // 2)
    for combination in possible_combinations:
        red_team_players = list(combination)
        blue_team_players = [player for player in players if player not in red_team_players]
        
        red_team_roles = assign_roles(red_team_players)
        blue_team_roles = assign_roles(blue_team_players)

        red_team = Team(
            top_laner=red_team_roles['top'],
            jungle=red_team_roles['jungle'],
            mid_laner=red_team_roles['mid'],
            bot_laner=red_team_roles['bot'],
            support=red_team_roles['support']
        )

        blue_team = Team(
            top_laner=blue_team_roles['top'],
            jungle=blue_team_roles['jungle'],
            mid_laner=blue_team_roles['mid'],
            bot_laner=blue_team_roles['bot'],
            support=blue_team_roles['support']
        )

        if validate_team_matchup(red_team, blue_team, degree):
            return red_team, blue_team

    return None, None

# This is the primary team formation method
def balance_teams(players):
    red_team, blue_team = find_balanced_teams(players, 1)
    
    attempts = 1
    while red_team is None or blue_team is None:
        if attempts <= 10:
            red_team, blue_team = find_balanced_teams(players, 1)
        elif 20 <= attempts > 10:
            red_team, blue_team = find_balanced_teams(players, 2)
        elif attempts > 20:
            return "Teams are not balanced. Please adjust priorities or tiers."    

        attempts += 1

    return blue_team, red_team

#Method to take users in the player role and pull their preferences to pass to the create_teams method
def create_playerlist(player_users):
    try:
        player_list = []
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        placeholders = ', '.join('?' for _ in player_users)
        query = f"""
            SELECT 
                CASE WHEN COALESCE(tieroverride,0) = 0 THEN 
                    CASE lolRank
                    WHEN 'Bronze' THEN 9
                    WHEN 'Silver' THEN 8 
                    WHEN 'Gold' THEN 7 
                    WHEN 'Platinum' THEN 6 
                    WHEN 'Emerald' THEN 5 
                    WHEN 'Diamond' THEN 4 
                    WHEN 'Master' THEN 3 
                    WHEN 'Grandmaster' THEN 2 
                    WHEN 'Challenger' THEN 1 
                    END 
                ELSE tieroverride
                END Tier
                , RiotID
                , discordID
                , SUBSTRING(preferences, 1, 1) AS top_priority
                , SUBSTRING(preferences, 2, 1) AS jungle_priority
                , SUBSTRING(preferences, 3, 1) AS mid_priority
                , SUBSTRING(preferences, 4, 1) AS bot_priority
                , SUBSTRING(preferences, 5, 1) AS support_priority
            FROM Player WHERE discordID IN ({placeholders})
            ORDER BY Tier"""

        cur.execute(query, player_users)
        data = cur.fetchall()
        for row in data:
            player_list.append(Player(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]))

        return player_list
    
    except sqlite3.Error as e:
        print(f"Terminating due to database team creation error: {e}")
        return

    finally:
        cur.close()
        dbconn.close()    

#Method to update a game with the winner
def update_win(lobby, winner):
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        query = f"UPDATE Games SET isComplete = 1, gameWinner = ? WHERE isComplete = 0 AND gameLobby = ?"
        cur.execute(query, [winner.upper(), lobby])
        dbconn.commit()
    
        return True
    except sqlite3.Error as e:
        print(f"Terminating due to database team win error: {e}")
        return False

    finally:
        cur.close()
        dbconn.close() 

#endregion METHODS



#region COMMANDS

#Command to update player's league of legends ID
@tree.command(
    name = 'riotid',
    description = 'Update your Riot ID <Game Name><#Tagline>',
    guild = discord.Object(GUILD))
async def riotid(interaction, id: str):
    register_player()
    update_riotid(interaction, id)
    await interaction.response.send_message(f'Your League of Legends ID has been updated to {id}.', ephemeral=True)

#Command to start check-in
@tree.command(
    name = 'checkin',
    description = 'Initiate Tournament Check-In.  Add timeout in seconds or use the default of 900 - 15 minutes.',
    guild = discord.Object(GUILD))
async def checkin(interaction, timeout: int=900):
    view = CheckinButtons(timeout=timeout)
    await interaction.response.send_message(f'Check-In for the tournament has started! You have {timeout//60} minutes to check-in.', view = view)

#Command to set preferences to fill (44444 is used)
@tree.command(
        name = 'fill',
        description= 'Set your position preferences to fill.',
        guild = discord.Object(GUILD))
async def fill(interaction):
    register_player(interaction)
    save_preference(interaction, "Fill - 44444")
    await interaction.response.send_message("Your preference has been set to fill", ephemeral=True)

#Command to update position preferences
@tree.command(
        name = 'roleselect',
        description= 'Update your role preferences.',
        guild = discord.Object(GUILD))
async def roleselect(interaction):
    register_player(interaction)
    embed = discord.Embed(title="Select your role preferences (1 (high) to 5 (never))", 
                          description=get_preferences(interaction), color=0x00ff00)
    view = DropdownView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

#Command to start volunteer
@tree.command(
    name = 'volunteer',
    description = 'initiate check for volunteers',
    guild = discord.Object(GUILD))
async def volunteer(interaction):
    view = volunteerButtons()
    await interaction.response.send_message('The Volunteer check has started! You have 15 minutes to volunteer if you wish to sit out', view = view)

@tree.command(
        name = 'toxicity',
        description = 'Give a user a point of toxicity.',
        guild = discord.Object(GUILD))
async def toxicity(interaction: discord.Interaction, discord_username: str):
    try:
        await interaction.response.defer(ephemeral = True)
        await asyncio.sleep(1)
        found_user = update_toxicity(interaction = interaction, discord_username = discord_username)
        if found_user:
            await interaction.followup.send(f"{discord_username}'s toxicity point has been updated.")
        else:
            await interaction.followup.send(f"{discord_username} could not be found.")
    except Exception as e:
        print(f'An error occured: {e}')

#Slash command to remove all users from the Player and Volunteer role.
@tree.command(
    name = 'clear',
    description = 'Remove all users from Players and Volunteer roles.',
    guild = discord.Object(GUILD))
async def remove(interaction: discord.Interaction):
    try:
        player = get(interaction.guild.roles, name = 'Player')
        volunteer = get(interaction.guild.roles, name = 'Volunteer')
        await interaction.response.defer(ephemeral = True)
        await asyncio.sleep(1)
        for user in interaction.guild.members:
            if player in user.roles:
                await user.remove_roles(player)
            if volunteer in user.roles:
                await user.remove_roles(volunteer)
        await interaction.followup.send('All users have been removed from roles.')
    except Exception as e:
        print(f'An error occured: {e}')

#Slash command to find and count all of the players and volunteers
@tree.command(
        name='players',
        description='Find all players and volunteers currently enrolled in the game',
        guild = discord.Object(GUILD))
async def players(interaction: discord.Interaction):
    try:
        player_users = []
        player = get(interaction.guild.roles, name = 'Player')
        for user in interaction.guild.members:
            if player in user.roles:
                player_users.append(user.name)
        
        #Finds all volunteers in discord, adds them to a list
        volunteer_users = []
        volunteer = get(interaction.guild.roles, name = 'Volunteer')
        for user in interaction.guild.members:
            if volunteer in user.roles:
                volunteer_users.append(user.name)

        player_count = sum(1 for user in interaction.guild.members if player in user.roles)
        volunteer_count = sum(1 for user in interaction.guild.members if volunteer in user.roles)

        #Embed to display all users who volunteered to sit out.
        embedPlayers = discord.Embed(color = discord.Color.green(), title = 'Total Players')
        embedPlayers.set_footer(text = f'Total players: {player_count}')
        for pl in player_users:
            embedPlayers.add_field(name = '', value = pl)

        embedVolunteers = discord.Embed(color = discord.Color.orange(), title = 'Total Volunteers')
        embedVolunteers.set_footer(text = f'Total volunteers: {volunteer_count}')
        for vol in volunteer_users:
            embedVolunteers.add_field(name = '', value = vol)
        
        next_increment = 10 - (player_count % 10)
        message = ''
        if player_count == 10:
            message += "There is a full lobby with 10 players!"
            embedMessage = discord.Embed(color = discord.Color.dark_green(), title = 'Players/Volunteers')
            embedMessage.add_field(name = '', value = message)
        elif next_increment==10 and player_count!=0:
            message += "There are multiple full lobbies ready!"
            embedMessage = discord.Embed(color = discord.Color.dark_green(), title = 'Players/Volunteers')
            embedMessage.add_field(name = '', value = message)
        elif player_count < 10:
            message += "A full lobby requires at least 10 players!"
            embedMessage = discord.Embed(color = discord.Color.dark_red(), title = 'Players/Volunteers')
            embedMessage.add_field(name = '', value = message)
        else:
            message += f"For a full lobby {next_increment} players are needed or {10-next_increment} volunteers are needed!"
            embedMessage = discord.Embed(color = discord.Color.dark_red(), title = 'Players/Volunteers')
            embedMessage.add_field(name = '', value = message)

        await interaction.response.send_message(embeds = [embedMessage, embedPlayers, embedVolunteers])
    except Exception as e:
        print(f'An error occured: {e}')

#Slash command to create teams
@tree.command(
    name = 'matchmake',
    description = "Form teams for all players enrolled in the game.",
    guild = discord.Object(GUILD))
async def matchmake(interaction: discord.Interaction, match_number: int):
    embedLobby2 = None
    embedLobby3 = None

    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        query = "SELECT EXISTS (SELECT * FROM Games WHERE isComplete = 0)"
        cur.execute(query)
        result = cur.fetchone()

        if result[0] != 0:
            await interaction.response.send_message('There are one or more incomplete games that need to be closed, see /activegames', ephemeral = True)
            return

        query = "SELECT EXISTS (SELECT * FROM Games WHERE gameNumber = ? and gameDate = DATE('now'))"
        cur.execute(query, [match_number,])
        result = cur.fetchone()

        if result[0] != 0:
            await interaction.response.send_message(f'Match number {match_number} has already been used today', ephemeral = True)
            return

        #Finds all players in discord, adds them to a list
        player_role = get(interaction.guild.roles, name='Player')
        player_users = [member.id for member in player_role.members]

        #Finds all volunteers in discord, adds them to a list
        volunteer_role = get(interaction.guild.roles, name='Volunteer')
        volunteer_users = [member.name for member in volunteer_role.members]
        volunteer_ids = [member.id for member in volunteer_role.members]

    #region TESTCODE
    ############################################################################################################
    #   TESTING ONLY
        player_users = [500012,500028,500001,500008,500015,500002,500018,500026,500027,500030,500042,500044,500014,
            500022,500032,500035,500023,500041,500040,500029]
        
        volunteer_ids = [500031,500020,500037,500007,500011,500017,500039,]
    ############################################################################################################
    #endregion TESTCODE

        if len(player_users) % 10 != 0:
            await interaction.response.send_message('There is not a multiple of 10 players, please see /players', ephemeral = True)
            return

        initial_list = create_playerlist(player_users)
        random.shuffle(initial_list)
        player_list = np.array_split(initial_list, int(len(initial_list)/10))

        for idx in range(1, int(len(player_users)/10)+1):
            query = '''INSERT INTO Games (gameDate, gameNumber, gameLobby, isComplete) VALUES (DATE('now'), ?, ?, 0)'''
            args = (match_number, idx,)
            cur.execute(query, args)
            dbconn.commit()
            gameID = cur.lastrowid
            blueteam, redteam = balance_teams(player_list[idx-1])

            if idx == 1:
                embedLobby1 = discord.Embed(color = discord.Color.from_rgb(255, 198, 41), title = f'Lobby 1 - Match: {match_number}')
                embedLobby1.add_field(name = 'Roles', value = '')
                embedLobby1.add_field(name = 'Blue Team', value = '')
                embedLobby1.add_field(name = 'Red Team', value = '')
                embedLobby1.add_field(name = '', value = 'Top Laner')
                embedLobby1.add_field(name = '', value = blueteam.top_laner.username)
                embedLobby1.add_field(name = '', value = redteam.top_laner.username)
                embedLobby1.add_field(name = '', value = 'Jungle')
                embedLobby1.add_field(name = '', value = blueteam.jungle.username)
                embedLobby1.add_field(name = '', value = redteam.jungle.username)
                embedLobby1.add_field(name = '', value = 'Mid Laner')
                embedLobby1.add_field(name = '', value = blueteam.mid_laner.username)
                embedLobby1.add_field(name = '', value = redteam.mid_laner.username)
                embedLobby1.add_field(name = '', value = 'Bot Laner')
                embedLobby1.add_field(name = '', value = blueteam.bot_laner.username)
                embedLobby1.add_field(name = '', value = redteam.bot_laner.username)
                embedLobby1.add_field(name = '', value = 'Support')
                embedLobby1.add_field(name = '', value = blueteam.support.username)
                embedLobby1.add_field(name = '', value = redteam.support.username)

                for vol in volunteer_ids:
                    query = '''INSERT INTO GameDetail (gameID, discordID, teamName, gamePosition, MVP) VALUES (?, ?, 'Participation', 'N/A', 0)'''
                    cur.execute(query, [gameID, vol])                
                    dbconn.commit()                
                               
            if idx == 2:
                embedLobby2 = discord.Embed(color = discord.Color.from_rgb(255, 198, 41), title = f'Lobby 2 - Match: {match_number}')
                embedLobby2.add_field(name = 'Roles', value = '')
                embedLobby2.add_field(name = 'Blue Team', value = '')
                embedLobby2.add_field(name = 'Red Team', value = '')
                embedLobby2.add_field(name = '', value = 'Top Laner')
                embedLobby2.add_field(name = '', value = blueteam.top_laner.username)
                embedLobby2.add_field(name = '', value = redteam.top_laner.username)
                embedLobby2.add_field(name = '', value = 'Jungle')
                embedLobby2.add_field(name = '', value = blueteam.jungle.username)
                embedLobby2.add_field(name = '', value = redteam.jungle.username)
                embedLobby2.add_field(name = '', value = 'Mid Laner')
                embedLobby2.add_field(name = '', value = blueteam.mid_laner.username)
                embedLobby2.add_field(name = '', value = redteam.mid_laner.username)
                embedLobby2.add_field(name = '', value = 'Bot Laner')
                embedLobby2.add_field(name = '', value = blueteam.bot_laner.username)
                embedLobby2.add_field(name = '', value = redteam.bot_laner.username)
                embedLobby2.add_field(name = '', value = 'Support')
                embedLobby2.add_field(name = '', value = blueteam.support.username)
                embedLobby2.add_field(name = '', value = redteam.support.username)
           
            if idx == 3:
                embedLobby3 = discord.Embed(color = discord.Color.from_rgb(255, 198, 41), title = f'Lobby 2 - Match: {match_number}')
                embedLobby3.add_field(name = 'Roles', value = '')
                embedLobby3.add_field(name = 'Blue Team', value = '')
                embedLobby3.add_field(name = 'Red Team', value = '')
                embedLobby3.add_field(name = '', value = 'Top Laner')
                embedLobby3.add_field(name = '', value = blueteam.top_laner.username)
                embedLobby3.add_field(name = '', value = redteam.top_laner.username)
                embedLobby3.add_field(name = '', value = 'Jungle')
                embedLobby3.add_field(name = '', value = blueteam.jungle.username)
                embedLobby3.add_field(name = '', value = redteam.jungle.username)
                embedLobby3.add_field(name = '', value = 'Mid Laner')
                embedLobby3.add_field(name = '', value = blueteam.mid_laner.username)
                embedLobby3.add_field(name = '', value = redteam.mid_laner.username)
                embedLobby3.add_field(name = '', value = 'Bot Laner')
                embedLobby3.add_field(name = '', value = blueteam.bot_laner.username)
                embedLobby3.add_field(name = '', value = redteam.bot_laner.username)
                embedLobby3.add_field(name = '', value = 'Support')
                embedLobby3.add_field(name = '', value = blueteam.support.username)
                embedLobby3.add_field(name = '', value = redteam.support.username)

            query = '''INSERT INTO GameDetail (gameID, discordID, teamName, gamePosition, MVP) VALUES (?, ?, ?, ?, 0)'''
            cur.execute(query, [gameID, redteam.top_laner.discord_id, "Red", "TOP"])
            cur.execute(query, [gameID, redteam.jungle.discord_id, "Red", "JUN"])
            cur.execute(query, [gameID, redteam.mid_laner.discord_id, "Red", "MID"])
            cur.execute(query, [gameID, redteam.bot_laner.discord_id, "Red", "ADC"])
            cur.execute(query, [gameID, redteam.support.discord_id, "Red", "SUP"])
            cur.execute(query, [gameID, blueteam.top_laner.discord_id, "Blue", "TOP"])
            cur.execute(query, [gameID, blueteam.jungle.discord_id, "Blue", "JUN"])
            cur.execute(query, [gameID, blueteam.mid_laner.discord_id, "Blue", "MID"])
            cur.execute(query, [gameID, blueteam.bot_laner.discord_id, "Blue", "ADC"])
            cur.execute(query, [gameID, blueteam.support.discord_id, "Blue", "SUP"])                
            dbconn.commit()

        #Embed to display all users who volunteered to sit out.
        embedVol = discord.Embed(color = discord.Color.blurple(), title = 'Volunteers - Match: ' + str(match_number))
        for vol in volunteer_users:
            embedVol.add_field(name = '', value = vol)
        if not volunteer_users:
            embedVol.add_field(name = '', value = 'No volunteers.')

        if embedLobby2 == None:
            await interaction.response.send_message( embeds = [embedVol, embedLobby1])
        elif embedLobby2 == None and not volunteer_users:
            await interaction.response.send_message( embeds = embedLobby1)
        elif embedLobby3 == None:
            await interaction.response.send_message( embeds = [embedVol, embedLobby1, embedLobby2])
        elif embedLobby3 == None and not volunteer_users:
            await interaction.response.send_message( embeds = [embedLobby1, embedLobby2])
        elif volunteer_users == None:
            await interaction.response.send_message( embeds = [embedLobby1, embedLobby2, embedLobby3])
        else:
            await interaction.response.send_message( embeds = [embedVol, embedLobby1, embedLobby2, embedLobby3])

    except Exception as e:
        print(f'An error occured: {e}')

#Slash command to end a match
@tree.command(
    name = 'win',
    description = "Set the winning team for open games by providing the lobby number and winning team color",
    guild = discord.Object(GUILD)
    # ,options=[
    #     create_option(
    #         name="choice",
    #         description="Your choice",
    #         option_type=3,  # 3 is the type for string
    #         required=True,
    #         choices=[
    #             create_choice(name="Option 1", value="option1"),
    #             create_choice(name="Option 2", value="option2")
    #         ])]
    )
async def win(interaction: discord.Interaction, lobby: int, winner: str):
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        query = 'SELECT EXISTS(SELECT gameID FROM Games WHERE isComplete = 0 AND gameLobby = ?)'
        cur.execute(query, [lobby])
        data = cur.fetchone()
        if data[0] != 1:
            await interaction.response.send_message(f"Lobby #{lobby} is not an active game, see /activegames", ephemeral=True)
            return
        
    except sqlite3.Error as e:
        print(f"Terminating due to database active games error: {e}")
        return
    
    finally:
        cur.close()
        dbconn.close() 
    
    if (winner.lower() != "red" and winner.lower() != "blue"):
        await interaction.response.send_message(f"{winner} is not a team name, choose blue or red", ephemeral=True)
        return
    
    if(update_win(lobby, winner)):
        await interaction.response.send_message(f"The winner for Lobby {lobby} has been set for the {winner} team!")

#Slash command to see active games
@tree.command(
    name = 'activegames',
    description = "Shows all games that have not been closed with /win",
    guild = discord.Object(GUILD))
async def activegames(interaction: discord.Interaction):
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        query = f"SELECT * FROM Games WHERE isComplete = 0"
        cur.execute(query)
        data = cur.fetchall()
    
        embedGames = discord.Embed(color = discord.Color.green(), title = 'Active Games')
        embedGames.set_footer(text = f'Total games: {len(data)}')
        for row in data:
            embedGames.add_field(name = '', value = f"Date:{row[1]}")
            embedGames.add_field(name = '', value = f"Match #{row[2]}")
            embedGames.add_field(name = '', value = f"Lobby #{row[3]}")

        await interaction.response.send_message(embed = embedGames)
        
    except sqlite3.Error as e:
        print(f"Terminating due to database active games error: {e}")

    finally:
        cur.close()
        dbconn.close() 


"""
@tree.command(
    name='votemvp',
    description='Vote for the mvp of your match',
    guild = discord.Object(GUILD))
async def voteMVP(interaction: discord.Interaction, player: str):
    await interaction.response.defer(ephemeral=True)
    asyncio.sleep(1)
    found_player = check_player(interaction = interaction, discord_username = player)
    channel = client.get_channel(1207123664168820736)
    user = interaction.user
    if found_player:
        await interaction.followup.send(f'You have voted for {player} to be MVP of the match')
        await channel.send(f'{user} has voted - MVP: {player}')
    else:
        await interaction.followup.send('This player could not be found in the spreadsheet')
"""
#endregion COMMANDS

#logging.getLogger('discord.gateway').addFilter(GatewayEventFilter())

#starts the bot
client.run(TOKEN)
