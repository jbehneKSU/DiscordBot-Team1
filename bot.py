import asyncio
import discord
import os
from dotenv import load_dotenv, find_dotenv
from discord import app_commands
from discord.utils import get
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import google.generativeai as genai
import csv, io, json
from datetime import datetime
# from discord.ext import commands
import sqlite3
import random
# from operator import itemgetter
import itertools
import numpy as np
import requests
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

# Variables set at startup that will not change
TOKEN = os.getenv('BOT_TOKEN') #Gets the bot's password token from the .env file and sets it to TOKEN.
GUILD = os.getenv('GUILD_ID') #Gets the server's id from the .env file and sets it to GUILD.
SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID') #Gets the Google Sheets ID from the .env file and sets it to SHEETS_ID.
SHEETS_NAME = os.getenv('GOOGLE_SHEETS_NAME') #Gets the google sheets name from the .env and sets it to SHEETS_NAME
SCOPES = ['https://www.googleapis.com/auth/spreadsheets'] #Allows the app to read and write to the google sheet.
SERVICE_ACCOUNT_FILE = 'token.json' #Location of Google Sheets credential file
RIOT_API_KEY = os.getenv('RIOT_API_KEY') #Gets the Riot API Key from the .env and sets it to RIOT_API_KEY
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') #Gets the API key for Google Gemini API

# Global variables set at startup and can be changed via commands
MAX_DEGREE_TIER = 2 #This number is used to determine how far apart in tiers players in opposing lanes can be during matchmaking
USE_RANDOM_SORT = True #This determines whether the player list is shuffled or sorted by tier 
USE_AI_MATCHMAKE = False #This determines whether team formation is done using AI or the Python methods

# Create credentials object for Google sheets
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Build the service object for Google sheets
service = build('sheets', 'v4', credentials=credentials)

# Set the Gemini AI API Key
genai.configure(api_key=GEMINI_API_KEY)

# on_ready event for script startup
@client.event
async def on_ready():
    # Global variables set at startup and can be changed via commands
    global MAX_DEGREE_TIER
    MAX_DEGREE_TIER = 2 #This number is used to determine how far apart in tiers players in opposing lanes can be during matchmaking
    global USE_RANDOM_SORT
    USE_RANDOM_SORT = True #This determines whether the player list is shuffled or sorted by tier 
    global USE_AI_MATCHMAKE
    USE_AI_MATCHMAKE = False #This determines whether team formation is done using AI or the Python methods

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
class PreferenceDropdown(discord.ui.Select):
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
class PreferenceDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(PreferenceDropdown("Top"))
        self.add_item(PreferenceDropdown("Jng"))
        self.add_item(PreferenceDropdown("Mid"))
        self.add_item(PreferenceDropdown("ADC"))
        self.add_item(PreferenceDropdown("Sup"))
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
        rankstatus, rank = update_riot_rank(interaction)

        if player in member.roles:
            await interaction.response.edit_message(view = self)
            await interaction.followup.send('You have already checked in.', ephemeral=True)
            return "Is already checked in"
        await member.add_roles(player)
        await interaction.response.edit_message(view = self)

        if rankstatus:
            await interaction.followup.send(f'You have checked in with Riot ID "{riotID}" and your Rank was updated to {rank}!  Be sure to check your /roleselect and update your /riotID if needed.', ephemeral = True)
        else:
            await interaction.followup.send(f'You have checked in with Riot ID "{riotID}" but your Rank could not be found!  Be sure to check your /roleselect and update your /riotID if needed.', ephemeral = True)

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

#Checkin button class for checking in to tournaments.
class ExportButtons(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(
            label = "Export Players",
            style = discord.ButtonStyle.green)
    async def export_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        today = datetime.now()
        sheets_export_players("Players_" + str(today.strftime('%m%d%Y')))
        await interaction.response.edit_message(view = self)
        await interaction.followup.send('Player data exported.', ephemeral=True)

    @discord.ui.button(
            label = "Export Points",
            style = discord.ButtonStyle.green)
    async def export_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        today = datetime.now()
        sheets_export_points("Points" + str(today.strftime('%m%d%Y')))
        await interaction.response.edit_message(view = self)
        await interaction.followup.send('Points data exported.', ephemeral=True)   
        
    @discord.ui.button(
            label = "Export Games",
            style = discord.ButtonStyle.green)
    async def export_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        sheets_export_games()
        await interaction.followup.send('Game data exported.', ephemeral=True)


#endregion CLASSES


#region METHODS

#Method to cleanup database game entries if a matchmake command fails
def reset_db_match(match: int):
    try:
        # Create database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Execute query to get all open lobbies for the failed match
        query = "SELECT gameID FROM Games WHERE GameNumber = ? AND gameDate = DATE('now')"
        args = (match,)
        cur.execute(query, args)
        result = cur.fetchall()

        # Loop through each GameID that was created
        for row in result:
            # First delete the game details for the GameID
            query = "DELETE FROM GameDetail WHERE GameID = ?"
            args = (row[0],)
            cur.execute(query, args)
            dbconn.commit()

            # Second delete the game record itself
            query = "DELETE FROM Games WHERE GameID = ?"
            args = (row[0],)
            cur.execute(query, args)
            dbconn.commit()        

    except sqlite3.Error as e:
        # Any errors in the database results in a failure
        print (f'Database error occurred purging incomplete match {match} : {e}')

    finally:
        # Close the database connection
        cur.close()
        dbconn.close()     

#Method to return a player's rank from the Riot API
def update_riot_rank(interaction: discord.Interaction):
    # Set the headers, including the API key
    headers = {'X-Riot-Token': RIOT_API_KEY}

    # Parms for id data returned by API calls
    puuid = ""
    id = ""

    # Parms for creating Riot ID from database
    game_name = ""
    tagline = ""

    try:
        # Create database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Execute query to get the RiotID for the player
        query = 'SELECT riotID FROM Player WHERE DiscordID = ?'
        args = (interaction.user.id,)
        cur.execute(query, args)
        result = cur.fetchone()

        # If result is empty then something went wrong finding the riotID
        if len(result) == 0:
            return False, ""

        # If the # character is missing then this is not a valid ID
        if '#' not in result[0]:
            return False, ""

        # Parse the name and tagline by splitting the Riot ID on the # character - this should be checked as valid at entry
        game_name = result[0].split("#")[0]
        tagline = result[0].split("#")[1]

    except sqlite3.Error as e:
        # Any errors in the database results in a failure
        print (f'Database error occurred getting riot ID: {e}')
        return False, ""

    finally:
        # Close the database connection
        cur.close()
        dbconn.close() 

    # Define the endpoint URL to get the player's PUUID 
    url = f'https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tagline}' 

    # Make the GET request to the Riot API
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response and set the puuid
        account_info = response.json()
        puuid = account_info['puuid']

    else:
        # Print the error and return False
        print(f'Error: {response.status_code} - {response.text}')
        return False, ""
        
    # Define the endpoint URL to get the player's Encrypted ID 
    url = f'https://na1.api.riotgames.com//lol/summoner/v4/summoners/by-puuid/{puuid}' 

    # Make the GET request to the Riot API
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response and set the id
        account_info = response.json()
        id = account_info['id']

    else:
        # Print the error and return False
        print(f'Error: {response.status_code} - {response.text}')
        return False, ""

    # Define the endpoint URL to get the player's rank information 
    url = f'https://na1.api.riotgames.com/lol/league/v4/entries/by-summoner/{id}' 

    # Make the GET request to the Riot API
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response and set the rank
        account_info = response.json()
        
        # If the player is not ranked the result will be empty so we will default to UNRANKED, otherwise use the returned rank
        if len(account_info) == 0:
            rank = "UNRANKED"
        else:
            rank = account_info[0]['tier']

        try:
            # Create the database connection
            dbconn = sqlite3.connect("bot.db")
            cur = dbconn.cursor()

            # Execute and commit the update to set the rank for the Discord player
            query = 'UPDATE Player SET lolRank = ? WHERE DiscordID = ?'
            args = (rank, interaction.user.id,)
            cur.execute(query, args)
            dbconn.commit()

            # At this point everything has worked and a True result is returned
            return True, rank
        
        except sqlite3.Error as e:
            # Any issues with the update will result in a False return
            print (f'Database error occurred getting riot ID: {e}')
            return False, ""

        finally:
            # Close the database connections
            cur.close()
            dbconn.close() 

    else:
        # Print the error
        print(f'Error: {response.status_code} - {response.text}')

    # If the code makes it to this point then there has been a critical failure and a False is returned
    return False, ""

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
                , SUM(CASE WHEN teamName != 'PARTICIPATION' THEN 1 ELSE 0 END) GamesPlayed
            FROM Player p
            INNER JOIN GameDetail gd ON gd.discordID = p.discordID
            INNER JOIN Games g ON g.gameID = gd.gameID
            GROUP BY p.discordID)

            SELECT t.discordID, p.discordName, riotID, Participation, Wins, MVPs, toxicity, GamesPlayed
                , CASE WHEN Wins = 0 OR GamesPlayed = 0 THEN 0 ELSE CAST(Wins AS float) / CAST(GamesPlayed AS float) END WinRatio
                , (Participation + Wins + MVPs - Toxicity) TotalPoints
            FROM totals t
            INNER JOIN Player p ON p.discordID = t.discordID""")        

        cur.execute("""CREATE VIEW IF NOT EXISTS vw_Player AS
                SELECT 
                CASE WHEN COALESCE(tieroverride,0) = 0 OR COALESCE(tieroverride,0) = '' THEN 
                    CASE LOWER(lolRank)
                    WHEN 'unranked' THEN 11
                    WHEN 'iron' THEN 10
                    WHEN 'bronze' THEN 9
                    WHEN 'silver' THEN 8 
                    WHEN 'gold' THEN 7 
                    WHEN 'platinum' THEN 6 
                    WHEN 'emerald' THEN 5 
                    WHEN 'diamond' THEN 4 
                    WHEN 'master' THEN 3 
                    WHEN 'grandmaster' THEN 2 
                    WHEN 'challenger' THEN 1 
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
            FROM Player""")

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
    if '#' not in id:
        return "Please enter your Riot ID as {gamename}#{tagline}"
    
    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Execute the update to set the Riot ID for the Discord player
        query = f"UPDATE Player SET riotID = ? WHERE discordID = ?"
        args = (id, interaction.user.id)
        cur.execute(query, args)
        dbconn.commit()
        
        return True
    
    except sqlite3.Error as e:
        # Print the error if anything goes wrong
        print (f'Database error occurred updating Riot ID: {e}')
        return "Error updating ID, please ensure you enter your riot ID as {gamename}#{tagline} "

    finally:
        # Close the database connection
        cur.close()
        dbconn.close()     

#Method to assign roles to players based on their preferred priority
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

#Method to create teams by sorting players by tier and then assigning roles
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

#Method that validates players are within 1 tier of each other and returns true or false
def validate_team_matchup(red_team, blue_team, degree):
    roles = ['top_laner', 'jungle', 'mid_laner', 'bot_laner', 'support']
    for role in roles:
        red_player = getattr(red_team, role)
        blue_player = getattr(blue_team, role)
        if abs(red_player.tier - blue_player.tier) > degree:
            return False
    return True

#Method to create and return a balanced team
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

#Method to create balanced teams using the MAX_DEGREE_TIER and USE_AI_MATCHMAKE to manipulate the results
def balance_teams(players):
    # If the USE_AI_MATCHMAKE is set to true the code will use Gemini to form the teams
    if USE_AI_MATCHMAKE:
        red_team, blue_team = gemini_ai_find_teams(players)
        
        if red_team is None or blue_team is None:
            return None, None
    
    # Otherwise teams will be created using the python methods
    else:
        # Attempt to create two teams with a degree of tier difference of 1
        red_team, blue_team = find_balanced_teams(players, 1)
        
        # Set # of attempts to 1
        attempts = 1

        # Begin a loop to run while either team is still not formed
        while red_team is None or blue_team is None:
            # Each iteration of the loop will try again, every 10 iterations will add one more degree of separation between opposing lanes
            red_team, blue_team = find_balanced_teams(players, attempts//10+1)

            # Increment the attempts counter
            attempts += 1

            # Check to see if the number of attempts has met or exceeded the max degree setting and exit if true
            if attempts >= MAX_DEGREE_TIER * 10 and (red_team is None or blue_team is None):
                return None, None    

    # If both teams were formed this method ends with returning both teams
    return blue_team, red_team

#Method to return balanced teams from Gemini AI
def gemini_ai_find_teams(players):
    try:
        # This will be used to create a JSON to send to the AI prompt - index is added to make matching the output back to the player easy
        playerdata = 'Index,Tier,Player,top_priority,jungle_priority,mid_priority,bot_priority,support_priority\n'
        
        # Iterate through the player list and add each player to the data string
        for idx, p in enumerate(players):
            playerdata += f"{idx},{p.tier},{p.username},{p.top_priority},{p.jungle_priority},{p.mid_priority},{p.bot_priority},{p.support_priority}\n"

        # This will create the JSON format of the playerdata string for the AI prompt
        reader = csv.DictReader(io.StringIO(playerdata))
        json_data = json.dumps(list(reader))

        # This var was used to try to enforce the AI to consider "tier" or "priority" as being more important but seemed to make little difference
        #weight = "tier"
        # This was the text included in the AI Prompt:
        #  Consider {weight} as the most important factor when assigning positions.

        # This is the AI prompt, including parameters and the JSON of player data, it will return a JSON output for the teams
        query = f'''
        Using the table below, create a league of legends blue and red team.  
        Lane priority uses 1 = most preferred, 2 = high preference, 3 = medium preference, 4 = low preference, and 5 = never assign. 
        Assume if the same values are used for multiple positions they are the same priority.
        Red and blue positions' players should be within 0 to {MAX_DEGREE_TIER} tier difference of each other.
        Return the result in JSON format.

        Return the result in the following JSON format:
        {{
        "blue_team": {{
            "top_laner": {{"index": 1, "username": "example", "tier": 3, "discordid": "12345", "priorities": "12345"}},
            "jungle": {{"index": 1, "username": "example", "tier": 4, "discordid": "12345", "priorities": "12345"}},
            "mid_laner": {{"index": 1, "username": "example", "tier": 2, "discordid": "12345", "priorities": "12345"}},
            "bot_laner": {{"index": 1, "username": "example", "tier": 1, "discordid": "12345", "priorities": "12345"}},
            "support": {{"index": 1, "username": "example", "tier": 5, "discordid": "12345", "priorities": "12345"}}
        }},
        "red_team": {{
            "top_laner": {{"index": 1, "username": "example", "tier": 3, "discordid": "12345", "priorities": "12345"}},
            "jungle": {{"index": 1, "username": "example", "tier": 4, "discordid": "12345", "priorities": "12345"}},
            "mid_laner": {{"index": 1, "username": "example", "tier": 2, "discordid": "12345", "priorities": "12345"}},
            "bot_laner": {{"index": 1, "username": "example", "tier": 1, "discordid": "12345", "priorities": "12345"}},
            "support": {{"index": 1, "username": "example", "tier": 5, "discordid": "12345", "priorities": "12345"}}
        }}
        }}

        {json_data}
        '''

        # Create the model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Send the prompt and capture the output
        response = model.generate_content(query)

        # The JSON response is not clean, this will help
        response_text = response.text.replace("`", "")
        response_text = response_text.replace("json", "")

        # After the JSON is cleaned up convert it to an array
        data = json.loads(response_text)

        # Use the index value of the player from the JSON to build each team
        blue_team = Team(players[data['blue_team']['top_laner']['index']],
                         players[data['blue_team']['jungle']['index']],
                         players[data['blue_team']['mid_laner']['index']],
                         players[data['blue_team']['bot_laner']['index']],
                         players[data['blue_team']['support']['index']])

        red_team = Team(players[data['red_team']['top_laner']['index']],
                         players[data['red_team']['jungle']['index']],
                         players[data['red_team']['mid_laner']['index']],
                         players[data['red_team']['bot_laner']['index']],
                         players[data['red_team']['support']['index']])

        # Return the completed teams
        return blue_team, red_team
    
    # If anything goes wrong then return None
    except Exception as e:
        print(f"Error occurred in AI generation: {e}")
        return None, None

#Method to take users in the player role and pull their preferences to pass to the create_teams method
def create_playerlist(player_users):
    try:
        # Create an empty array
        player_list = []

        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # This creates a string for the query to take x args based on player size to create the WHERE for player lookup
        placeholders = ', '.join('?' for _ in player_users)
        
        # This query will get the info from the database for all players
        query = f"""
            SELECT *
            FROM vw_Player WHERE discordID IN ({placeholders})
            ORDER BY Tier"""

        # Execute the query, iterate the results, and append the data to the array
        cur.execute(query, player_users)
        data = cur.fetchall()
        for row in data:
            player_list.append(Player(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]))

        # Return the player list
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
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # This query will set the game winner and isComplete for the passed lobby
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

#Method to check if a sheet exists, returns True/False
def sheet_exists(sheet_name):
    # Get spreadsheet metadata
    spreadsheet = service.spreadsheets().get(spreadsheetId=SHEETS_ID).execute()
    sheets = spreadsheet.get('sheets', [])

    # Check if the sheet name exists
    for sheet in sheets:
        if sheet['properties']['title'] == sheet_name:
            return True
    return False

#Method to create a sheet with the name passed in and a bool to clear the sheet if it already exists
def sheets_create(sheet_name, clear):
    # Check if the sheet name already exists, if not then create it
    if not sheet_exists(sheet_name):
        # Request body to add a new sheet
        request_body = {'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}

        # Call the API to add a new sheet
        response = service.spreadsheets().batchUpdate(spreadsheetId=SHEETS_ID,body=request_body).execute()

        # Get the new sheet's ID from the response and return this
        return response['replies'][0]['addSheet']['properties']['sheetId']
    
    # If the sheet name already exists check if the clear parm is True to delete the data
    elif clear:
        # Range to clear (for entire sheet, use "SheetName")
        range_to_clear = f'{sheet_name}'

        # Clear the data
        request_body = {}
        service.spreadsheets().values().clear(spreadsheetId=SHEETS_ID,range=range_to_clear,body=request_body).execute()

    # Get the sheet ID from the sheet name by looping through each sheet until it matches
    spreadsheet = service.spreadsheets().get(spreadsheetId=SHEETS_ID).execute()
    sheets = spreadsheet.get('sheets', [])
    for sheet in sheets:
        if sheet['properties']['title'] == sheet_name:
            return sheet['properties']['sheetId']

#Method to export the points data from the database to the sheet      
def sheets_export_points(sheet_name):
    # First check if the sheet exists yet, if yes clear it out
    sheets_create(sheet_name, True)
    
    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Query to get the points and player info
        query = "SELECT * FROM vw_Points"
        cur.execute(query)

        # Get the column names (headers)
        headers = [description[0] for description in cur.description]

        # Execute the query and capture the results
        rows = cur.fetchall()

        # Convert fetched data to a list of lists suitable for Google Sheets
        data = [list(map(str, row)) for row in rows]

        # Add headers if needed (optional)
        data.insert(0, headers)

        # Calculate the range based on data size
        start_cell = 'A1'
        end_cell = f'{chr(ord("A") + len(data[0]) - 1)}{len(data)}'
        range_name = f'{sheet_name}!{start_cell}:{end_cell}'

        # Request body for updating values
        body = {'values': data}

        # Write data to the sheet using the update method
        result = service.spreadsheets().values().update(spreadsheetId=SHEETS_ID,range=range_name,valueInputOption='RAW',body=body).execute()  

    except sqlite3.Error as e:
        print (f'Database error occurred: {e}')

    finally:
        cur.close()
        dbconn.close() 

#Method to export the player information from the database to the sheet
def sheets_export_players(sheet_name):
    # First check if the sheet exists yet, if yes clear it out
    sheets_create(sheet_name, True)

    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Query to get the information from the player table
        query = """SELECT Tier, lolRank, tieroverride, discordName, p.riotID, top_priority, jungle_priority, 
                mid_priority, bot_priority, support_priority 
                FROM vw_Player
                INNER JOIN Player p ON p.discordID = vw_Player.discordID"""
        cur.execute(query)

        # Get the column names (headers)
        headers = [description[0] for description in cur.description]

        # Execute the query and capture the results
        rows = cur.fetchall()

        # Convert fetched data to a list of lists suitable for Google Sheets
        data = [list(map(str, row)) for row in rows]

        # Add headers if needed (optional)
        data.insert(0, headers)

        # Calculate the range based on data size
        start_cell = 'A1'
        end_cell = f'{chr(ord("A") + len(data[0]) - 1)}{len(data)}'
        range_name = f'{sheet_name}!{start_cell}:{end_cell}'

        # Request body for updating values
        body = {'values': data}

        # Write data to the sheet using the update method
        result = service.spreadsheets().values().update(spreadsheetId=SHEETS_ID,range=range_name,valueInputOption='RAW',body=body).execute()  

    except sqlite3.Error as e:
        print (f'Database error occurred: {e}')

    finally:
        cur.close()
        dbconn.close() 

#Method to write a list of cell data to the given sheetId, used for bulk writes
def sheets_write_cells(sheetId, cell_data):
    # Prepare the data to be written
    requests = []
    
    # Iterate through each cell in the list and build the request
    for cell in cell_data:
        requests.append({
            'updateCells': {
                'range': {
                    'sheetId': sheetId,  
                    'startRowIndex': cell[0]['row'],
                    'endRowIndex': cell[0]['row'] + 1,
                    'startColumnIndex': cell[0]['col'],
                    'endColumnIndex': cell[0]['col'] + 1
                },
                'rows': [{
                    'values': [{
                        'userEnteredValue': {
                            'stringValue': cell[0]['value']
                        },
                        'userEnteredFormat': {
                            'backgroundColor': {
                                'red': cell[0]['color'].get('red', 0),
                                'green': cell[0]['color'].get('green', 0),
                                'blue': cell[0]['color'].get('blue', 0),
                            }
                        }
                    }]
                }],
                'fields': 'userEnteredValue,userEnteredFormat.backgroundColor'
            }
        })

    # Send the batchUpdate request
    body = {'requests': requests}
    service.spreadsheets().batchUpdate(spreadsheetId=SHEETS_ID,body=body).execute()

#Method to export all of the game details to sheets by month
def sheets_export_games():
    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Query to get the month and name from the Games table
        query = """SELECT DISTINCT strftime('%m', gameDate), 
                CASE strftime('%m', gameDate) 
                WHEN '01' THEN 'Jan_' || strftime('%Y', gameDate)
                WHEN '02' THEN 'Feb_' || strftime('%Y', gameDate)
                WHEN '03' THEN 'Mar_' || strftime('%Y', gameDate)
                WHEN '04' THEN 'Apr_' || strftime('%Y', gameDate)
                WHEN '05' THEN 'May_' || strftime('%Y', gameDate)
                WHEN '06' THEN 'Jun_' || strftime('%Y', gameDate)
                WHEN '07' THEN 'Jul_' || strftime('%Y', gameDate)
                WHEN '08' THEN 'Aug_' || strftime('%Y', gameDate)
                WHEN '09' THEN 'Sep_' || strftime('%Y', gameDate)
                WHEN '10' THEN 'Oct_' || strftime('%Y', gameDate)
                WHEN '11' THEN 'Nov_' || strftime('%Y', gameDate)
                WHEN '12' THEN 'Dec_' || strftime('%Y', gameDate)
                END
                FROM Games;"""
        cur.execute(query)
        months = cur.fetchall()

        # Loop #1 - iterate each month in Games
        for month in months:
            # Create an empty list for the cell data to write to the sheet
            celldata = []

            # Call the method to create a new sheet based on the month name with the clear flag if it exists + capture the sheet id output
            new_sheet_id = sheets_create(month[1], True)

            # Use the current month to query the dates games were played
            query = "SELECT DISTINCT gameDate FROM Games WHERE strftime('%m', gameDate) = ?;"
            cur.execute(query, [month[0],])
            days = cur.fetchall()

            # Loop #2 - iterate each day in the month of Games
            for day_idx, day in enumerate(days):
                # Set the starting position for the column the date is written, B1 = cell position 0, 1 - there are 7 cells between each date calculated by the index
                daycol = 1 + (day_idx * 7)

                # Add the date value to the cell data using a light green background (float of 0.0 to 1.0 created by dividing RGB by 255)
                celldata.append([{'row': 0, 'col': daycol, 'value': day[0], 'color': {'red': 82/255, 'green': 216/255, 'blue': 109/255}}])
            
                # Query to get the gameNumbers for the current day in the lop
                query = "SELECT DISTINCT gameNumber FROM Games WHERE gameDate = ?;"
                cur.execute(query, [day[0],])
                games = cur.fetchall()

                # Loop #3 - iterate each game number in the current day loop
                for game_idx, game in enumerate(games):
                    # The row of the game starts on 2 and has 9 spaces between each game in a day, calculated by the index * 9
                    gamerow = 2 + (game_idx * 9)

                    # The column of the game starts at 0 with 7 spaces between days, calculated by the index * 7
                    gamecol = 0 + (day_idx * 7)

                    # Append the cell with the game number to the list
                    celldata.append([{'row': gamerow, 'col': gamecol + 1, 'value': "Game " + str(game[0]), 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                    
                    # Append the position name cells to the list with a green background
                    celldata.append([{'row': gamerow + 3, 'col': gamecol, 'value': "Top", 'color': {'red': 193/255, 'green': 192/255, 'blue': 192/255}}])
                    celldata.append([{'row': gamerow + 4, 'col': gamecol, 'value': "Jng", 'color': {'red': 193/255, 'green': 192/255, 'blue': 192/255}}])
                    celldata.append([{'row': gamerow + 5, 'col': gamecol, 'value': "Mid", 'color': {'red': 193/255, 'green': 192/255, 'blue': 192/255}}])
                    celldata.append([{'row': gamerow + 6, 'col': gamecol, 'value': "ADC", 'color': {'red': 193/255, 'green': 192/255, 'blue': 192/255}}])
                    celldata.append([{'row': gamerow + 7, 'col': gamecol, 'value': "Sup", 'color': {'red': 193/255, 'green': 192/255, 'blue': 192/255}}])

                    # Query the lobbies and the winner for the current game number
                    query = "SELECT gameLobby, gameWinner FROM Games WHERE gameDate = ? and gameNumber = ?;"
                    cur.execute(query, [day[0], game[0]])
                    lobbies = cur.fetchall()

                    # Loop #4 - iterate each lobby in the current game
                    for lobby_idx, lobby in enumerate(lobbies):
                        # The lobby column starts at 1 with 2 spaces between, calculated by the index * 2.
                        # Additionally the current game column is added for each day in the loop
                        lobbycol = 1 + (lobby_idx * 2) + (gamecol)

                        # Append the lobby number to the cell list
                        celldata.append([{'row': gamerow + 1, 'col': lobbycol, 'value': "Lobby " + str(lobby[0]), 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                        
                        # Index 1 of lobby is the winner of the game, if it is blue this will fill the background of the blue team as the winner
                        if lobby[1] == "BLUE":
                            # Append the team names and background color for blue as the winner
                            celldata.append([{'row': gamerow + 2, 'col': lobbycol, 'value': "BLUE", 'color': {'red': 11/255, 'green': 178/255, 'blue': 0}}])
                            celldata.append([{'row': gamerow + 2, 'col': lobbycol + 1, 'value': "RED", 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                        
                        # If blue was not the winner we assume red was and add the background color
                        else:
                            # Append the team names and background color for red as the winner
                            celldata.append([{'row': gamerow + 2, 'col': lobbycol, 'value': "BLUE", 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                            celldata.append([{'row': gamerow + 2, 'col': lobbycol + 1, 'value': "RED", 'color': {'red': 11/255, 'green': 178/255, 'blue': 0}}])
                        
                        # Query the players for the team in the current lobby
                        # NOTE HERE - the assumption is the teams always return in order of Top, Jng, Mid, ADC, and Sup
                        query = """SELECT teamName, riotID, COALESCE(MVP, 0), gamePosition
                                FROM Games g
                                INNER JOIN GameDetail gd on gd.gameID = g.gameID
                                INNER JOIN Player p ON p.discordID = gd.discordID
                                WHERE gameDate = ? and gameNumber = ? and gameLobby = ?
                                AND teamName <> 'PARTICIPATION';"""
                        cur.execute(query, [day[0], game[0], lobby[0]])
                        teams = cur.fetchall()

                        # Set the starting row for red/blue, which is 3 spaces down from where the game row starts
                        bluerow = gamerow + 3
                        redrow = gamerow + 3

                        # Loop #5 - iterate through the players
                        for team_idx, team in enumerate(teams):
                            # First check is if this is the blue team AND the player was MVP
                            if team[0] == "BLUE" and team[2] == 1:
                                # Append the player with a gold background as the MVP to the cell data and increment the blue row to the next position
                                celldata.append([{'row': bluerow, 'col': lobbycol, 'value': team[1], 'color': {'red': 196/255, 'green': 214/255, 'blue': 0}}])
                                bluerow += 1
                            
                            # Next check if this is just a blue team player
                            elif team[0] == "BLUE":
                                # Append the player to the cell data and increment the blue row to the next position
                                celldata.append([{'row': bluerow, 'col': lobbycol, 'value': team[1], 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                                bluerow += 1
                            
                            # Next check if this is red team AND MVP
                            elif team[0] == "RED" and team[2] == 1:
                                # Append the player with a gold background as the MVP to the cell data and increment the red row to the next position
                                celldata.append([{'row': redrow, 'col': lobbycol + 1, 'value': team[1], 'color': {'red': 196/255, 'green': 214/255, 'blue': 0}}])
                                redrow += 1

                            # Finally check if this is red team
                            elif team[0] == "RED":
                                # Append the player to the cell data and increment the blue row to the next position
                                celldata.append([{'row': redrow, 'col': lobbycol + 1, 'value': team[1], 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                                redrow += 1                                

                    # Back out to loop #3 (game number) again - query to get the participation players
                    query = """SELECT riotID
                            FROM Games g
                            INNER JOIN GameDetail gd on gd.gameID = g.gameID
                            INNER JOIN Player p ON p.discordID = gd.discordID
                            WHERE gameDate = ? and gameNumber = ?
                            AND teamName = 'PARTICIPATION';"""
                    cur.execute(query, [day[0], game[0]])
                    participations = cur.fetchall()      

                    # The participation column starts 2 columns from the last lobby and 2 rows below the game number
                    partcol = lobbycol + 2
                    partrow = gamerow + 2

                    # Add the participation header and increment the row
                    celldata.append([{'row': partrow, 'col': partcol, 'value': "PARTICIPATION", 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                    partrow += 1

                    # Iterate the participation players 
                    for part_idx, participation in enumerate(participations):
                        # There is only room for 5 players without running into a new game below, when 5 is reached increment the column and reset row
                        if part_idx == 5:
                            partcol += 1
                            partrow = gamerow + 2

                        # Add the player row to the cell list and increment the row
                        celldata.append([{'row': partrow, 'col': partcol, 'value': participation[0], 'color': {'red': 1, 'green': 1, 'blue': 1}}])
                        partrow += 1
        
            # Now back out to Loop #1 (Month) - call the sheets write function and pass the sheet id captured above and the cell list data
            sheets_write_cells(new_sheet_id, celldata)

    except sqlite3.Error as e:
        print (f'Database error occurred: {e}')

    finally:
        cur.close()
        dbconn.close()     

#Method to determine if the user is an admin
def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator

#endregion METHODS



#region COMMANDS

#Command to update player's league of legends ID
@tree.command(
    name = 'riotid',
    description = 'Update your Riot ID <Game Name><#Tagline>',
    guild = discord.Object(GUILD))
async def riotid(interaction, id: str):
    # Make sure the player has been registered in the database
    register_player(interaction)

    # Update the Riot ID and capture the return of true or the error message to determine if it worked
    status = update_riotid(interaction, id)

    # Call the update rank method to set the player's rank from the Riot API, capture the true/false if it worked and the player's rank for output
    rankupdate, newrank = update_riot_rank(interaction)
    
    # If the Riot ID was successful then check the rank update next
    if (status == True):
        # If the rank update was successful, output success for both and indicate the values
        if rankupdate:
            await interaction.response.send_message(f'Your Riot ID has been updated to {id} and your Rank has been updated to {newrank}.', ephemeral=True)
        # If the ID was updated but not the rank
        else:
            await interaction.response.send_message(f'Your Riot ID has been updated to {id} but your Rank could not be found, please check the name.', ephemeral=True)
    # If the ID was not updated display the error
    else:
        await interaction.response.send_message(f'{status}', ephemeral=True)

#Command to start check-in
@tree.command(
    name = 'checkin',
    description = 'Initiate Tournament Check-In.  Add timeout in seconds or use the default of 900 - 15 minutes.',
    guild = discord.Object(GUILD))
async def checkin(interaction, timeout: int=900):
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    
    
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
    view = PreferenceDropdownView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

#Command to start volunteer
@tree.command(
    name = 'volunteer',
    description = 'initiate check for volunteers',
    guild = discord.Object(GUILD))
async def volunteer(interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    
    
    view = volunteerButtons()
    await interaction.response.send_message('The Volunteer check has started! You have 15 minutes to volunteer if you wish to sit out', view = view)

# Command to add a point of toxicity to a player
@tree.command(
        name = 'toxicity',
        description = 'Give a user a point of toxicity.',
        guild = discord.Object(GUILD))
async def toxicity(interaction: discord.Interaction, discord_username: str):
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    try:
        found_user = update_toxicity(interaction, discord_username)
        if found_user:
            await interaction.response.send_message(f"{discord_username}'s toxicity point has been updated.")
        else:
            await interaction.response.send_message(f"{discord_username} could not be found.")
    except Exception as e:
        print(f'An error occured: {e}')

#Slash command to remove all users from the Player and Volunteer role.
@tree.command(
    name = 'clear',
    description = 'Remove all users from Players and Volunteer roles.',
    guild = discord.Object(GUILD))
async def remove(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    

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
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    message = ''

    try:
        #Finds all players in discord, adds them to a list
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
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    
    
    # Create empty lobby vars for 2 and 3, 1 will always be created
    embedLobby2 = None
    embedLobby3 = None

    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Query to make sure games have been left actives, this ensures the win command is used after games are played
        query = "SELECT EXISTS (SELECT * FROM Games WHERE isComplete = 0)"
        cur.execute(query)
        result = cur.fetchone()

        # If EXISTS does not return a 0 there are games that have not been closed and the method ends
        if result[0] != 0:
            await interaction.response.send_message('There are one or more incomplete games that need to be closed, see /activegames', ephemeral = True)
            print("Matchmake command called with incomplete games still active.")
            return

        # Query to check if the match number has been used already today
        query = "SELECT EXISTS (SELECT * FROM Games WHERE gameNumber = ? and gameDate = DATE('now'))"
        cur.execute(query, [match_number,])
        result = cur.fetchone()

        # If EXISTS does not return a 0 then the given match number has already been used today and the method ends
        if result[0] != 0:
            await interaction.response.send_message(f'Match number {match_number} has already been used today', ephemeral = True)
            print("Matchmake command called using a match number that was already used for today.")
            return

        #Finds all players in discord, adds them to a list
        player_role = get(interaction.guild.roles, name='Player')
        player_users = [member.id for member in player_role.members]

        #Finds all volunteers in discord, adds them to a list.  _users is used for the embed out and _ids is used for the database
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

        # Ensure an even split of 10 players and end the method if not
        if len(player_users) % 10 != 0:
            await interaction.response.send_message('There is not a multiple of 10 players, please see /players', ephemeral = True)
            print("Matchmake command called without a correct multiple of players.")
            return

        # This passes the list of discord user IDs to the create_playerlist function to get the player data from the database as a list of Player class
        initial_list = create_playerlist(player_users)

        # This shuffle will help randomize teams as opposed to sorting them by tier which tended to create the same teams
        if USE_RANDOM_SORT:
            random.shuffle(initial_list)

        # Now create a list of lists of 10 players, this is how lobbies are created (10 = 1 lobby, 20 = 2 lobbies, 30 = 3 lobbies)
        player_list = np.array_split(initial_list, int(len(initial_list)/10))

        # AI response takes more than 3 seconds generally so responses must be handled with a defer
        if USE_AI_MATCHMAKE:
            await interaction.response.defer()

        # Loop through the list of list of Players to create 2 teams (blue/red) of 5 for each list.  
        # Len() uses +1 so that idx corresponds with the Lobby # (1,2,3)
        for idx in range(1, int(len(player_users)/10)+1):
            # Call the primary team creation function by passing the current list of 10 Players, this returns the two teams 
            # Because idx corresponds to Lobby# and the array is 0 based, subtract 1 from the lobby
            blueteam, redteam = balance_teams(player_list[idx-1])

            if blueteam is None or redteam is None:
                reset_db_match(match_number)
                
                # Response type will depend on whether AI is used - with defer this will not be ephmeral
                if USE_AI_MATCHMAKE:
                    await interaction.followup.send(f'Team could not be formed for Lobby #{idx}, please adjust role preference or tier scores and try again')
                else:
                    await interaction.response.send_message(f'Team could not be formed for Lobby #{idx}, please adjust role preference or tier scores and try again', ephemeral = True)
                print("Matchmake command failed to form a team.")
                return

            # Query to insert a new game using today's date, passing the game number from the input, the index of the loop for the lobby, and complete is 0
            query = '''INSERT INTO Games (gameDate, gameNumber, gameLobby, isComplete) VALUES (DATE('now'), ?, ?, 0)'''
            args = (match_number, idx,)
            cur.execute(query, args)
            dbconn.commit()

            # This will capture the ID of the game that was just inserted to be used for the GameDetail table
            gameID = cur.lastrowid

            # This IF will execute if the lobby # is 1 and build the Lobby 1 embed and insert the volunteers into the Lobby 1 game
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

                # Loop the volunteer id list
                for vol in volunteer_ids:
                    # Query to insert the game ID and Discord ID to GameDetail for this game
                    query = '''INSERT INTO GameDetail (gameID, discordID, teamName, gamePosition, MVP) VALUES (?, ?, 'PARTICIPATION', 'N/A', 0)'''
                    cur.execute(query, [gameID, vol])                
                    dbconn.commit()                

            # This IF will execute if the lobby # is 2 and build the Lobby 2 embed 
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
           
            # This IF will execute if the lobby # is 3 and build the Lobby 3 embed 
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

            # After the lobby embed is created, this query will insert the players into the GameDetail table
            query = '''INSERT INTO GameDetail (gameID, discordID, teamName, gamePosition, MVP) VALUES (?, ?, ?, ?, 0)'''
            cur.execute(query, [gameID, redteam.top_laner.discord_id, "RED", "TOP"])
            cur.execute(query, [gameID, redteam.jungle.discord_id, "RED", "JUN"])
            cur.execute(query, [gameID, redteam.mid_laner.discord_id, "RED", "MID"])
            cur.execute(query, [gameID, redteam.bot_laner.discord_id, "RED", "ADC"])
            cur.execute(query, [gameID, redteam.support.discord_id, "RED", "SUP"])
            cur.execute(query, [gameID, blueteam.top_laner.discord_id, "BLUE", "TOP"])
            cur.execute(query, [gameID, blueteam.jungle.discord_id, "BLUE", "JUN"])
            cur.execute(query, [gameID, blueteam.mid_laner.discord_id, "BLUE", "MID"])
            cur.execute(query, [gameID, blueteam.bot_laner.discord_id, "BLUE", "ADC"])
            cur.execute(query, [gameID, blueteam.support.discord_id, "BLUE", "SUP"])                
            dbconn.commit()

        #Embed to display all users who volunteered to sit out.
        embedVol = discord.Embed(color = discord.Color.blurple(), title = 'Volunteers - Match: ' + str(match_number))
        for vol in volunteer_users:
            embedVol.add_field(name = '', value = vol)
        if not volunteer_users:
            embedVol.add_field(name = '', value = 'No volunteers.')

        # This block determines which Lobbies exist and displays the correct embeds.
        # This could likely be done better, but currently works and is not causing performance issues
        if embedLobby2 == None:
            if USE_AI_MATCHMAKE:
                await interaction.followup.send( embeds = [embedVol, embedLobby1])
            else:
                await interaction.response.send_message( embeds = [embedVol, embedLobby1])

        elif embedLobby2 == None and not volunteer_users:
            if USE_AI_MATCHMAKE:
                await interaction.followup.send( embeds = embedLobby1)
            else:
                await interaction.response.send_message( embeds = embedLobby1)
        elif embedLobby3 == None:
            if USE_AI_MATCHMAKE:
                await interaction.followup.send( embeds = [embedVol, embedLobby1, embedLobby2])
            else:
                await interaction.response.send_message( embeds = [embedVol, embedLobby1, embedLobby2])
        elif embedLobby3 == None and not volunteer_users:
            if USE_AI_MATCHMAKE:
                await interaction.followup.send( embeds = [embedLobby1, embedLobby2])
            else:
                await interaction.response.send_message( embeds = [embedLobby1, embedLobby2])
        elif volunteer_users == None:
            if USE_AI_MATCHMAKE:
                await interaction.followup.send( embeds = [embedLobby1, embedLobby2, embedLobby3])
            else:
                await interaction.response.send_message( embeds = [embedLobby1, embedLobby2, embedLobby3])
        else:
            if USE_AI_MATCHMAKE:
                await interaction.followup.send( embeds = [embedVol, embedLobby1, embedLobby2, embedLobby3])
            else:
                await interaction.response.send_message( embeds = [embedVol, embedLobby1, embedLobby2, embedLobby3])

    except Exception as e:
        print(f'An error occured: {e}')

    finally:
        cur.close()
        dbconn.close()

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
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    
    
    try:
        # Create database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Create query to check if the passed Lobby # is a valid open game
        query = 'SELECT EXISTS(SELECT gameID FROM Games WHERE isComplete = 0 AND gameLobby = ?)'
        cur.execute(query, [lobby])
        data = cur.fetchone()

        # If the EXISTS returns a 0 then there is no active game for the lobby provided and the method ends
        if data[0] != 1:
            await interaction.response.send_message(f"Lobby #{lobby} is not an active game, see /activegames", ephemeral=True)
            return
        
    # Catch SQL errors and print a message to the console and Discord
    except sqlite3.Error as e:
        print(f"Terminating due to database active games error: {e}")
        await interaction.response.send_message(f"Failed due to database error {e}", ephemeral=True)
        return
    
    finally:
        cur.close()
        dbconn.close() 
    
    # Data validation on the winning team name to make sure the user sent blue or red
    if (winner.lower() != "red" and winner.lower() != "blue"):
        await interaction.response.send_message(f"{winner} is not a team name, choose blue or red", ephemeral=True)
        return
    
    # By this point, all data validation is clear and the update_win method is called to update the database
    # The method returns true/false, if true it outputs the message the update was made, if false is returned the method outputs the error
    if(update_win(lobby, winner)):
        await interaction.response.send_message(f"The winner for Lobby {lobby} has been set for the {winner} team!")

#Slash command to see active games
@tree.command(
    name = 'activegames',
    description = "Shows all games that have not been closed with /win",
    guild = discord.Object(GUILD))
async def activegames(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    try:
        # Create database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # SQL query for active games, no args needed
        query = f"SELECT * FROM Games WHERE isComplete = 0"
        cur.execute(query)
        data = cur.fetchall()
    
        # Create the embed for displaying the game information, will show 0 if no games are returned
        embedGames = discord.Embed(color = discord.Color.green(), title = 'Active Games')
        embedGames.set_footer(text = f'Total games: {len(data)}')

        # Loop the data returned and add a line for each active game to the embed
        for row in data:
            embedGames.add_field(name = '', value = f"Date:{row[1]}")
            embedGames.add_field(name = '', value = f"Match #{row[2]}")
            embedGames.add_field(name = '', value = f"Lobby #{row[3]}")

        # Output the embed
        await interaction.response.send_message(embed = embedGames)
        
    # Catch sql errors, print to console and output message to Discord
    except sqlite3.Error as e:
        print(f"Terminating due to database active games error: {e}")
        await interaction.response.send_message(f"Failed due to database error {e}", ephemeral=True)

    finally:
        cur.close()
        dbconn.close() 

#Command to set preferences to fill (44444 is used)
@tree.command(
        name = 'export',
        description= 'Export database to Google sheets.',
        guild = discord.Object(GUILD))
async def export(interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    view = ExportButtons()
    await interaction.response.send_message(f'Use the buttons below to export the database to Google sheets', view = view, ephemeral=True)

#Slash command to see and change admin settings
@tree.command(
    name = 'settings',
    description = "Testing placeholder for viewing and changing settings",
    guild = discord.Object(GUILD))
async def settings(interaction: discord.Interaction, use_ai: str = ''):
    await interaction.response.defer(ephemeral=True)
    
    if not is_admin(interaction):
        await interaction.followup.send("This command is only for administrators.", ephemeral=True)
        return
    
    if use_ai != '' and (use_ai.lower() == 'true' or use_ai.lower() == 'false'):
        if use_ai.lower() == 'true':
            global USE_AI_MATCHMAKE
            USE_AI_MATCHMAKE = True
        else:
            USE_AI_MATCHMAKE = False

        await interaction.followup.send(f"USE_AI_MATCHMAKE has been set to {USE_AI_MATCHMAKE}", ephemeral=True)
        return        

    # Create the embed for displaying the game information, will show 0 if no games are returned
    embedGames = discord.Embed(color = discord.Color.green(), title = 'Bot Settings')

    # Loop the data returned and add a line for each active game to the embed
    embedGames.add_field(name = 'USE_AI_MATCHMAKE', value = f"{USE_AI_MATCHMAKE}")
    embedGames.add_field(name = 'MAX_DEGREE_TIER', value = f"{MAX_DEGREE_TIER}")
    embedGames.add_field(name = 'USE_RANDOM_SORT', value = f"{USE_RANDOM_SORT}")

    # Output the embed
    await interaction.followup.send(embed = embedGames, ephemeral=True)




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
