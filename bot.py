import asyncio
import discord
import os
import shutil
from dotenv import load_dotenv, find_dotenv
from discord import app_commands
from discord.utils import get
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import google.generativeai as genai
import csv, io, json
from datetime import datetime
import time
import sqlite3
import random
import itertools
import numpy as np
import requests

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
SCOPES = ['https://www.googleapis.com/auth/spreadsheets'] #Allows the app to read and write to the google sheet.
SERVICE_ACCOUNT_FILE = 'token.json' #Location of Google Sheets credential file
RIOT_API_KEY = os.getenv('RIOT_API_KEY') #Gets the Riot API Key from the .env and sets it to RIOT_API_KEY
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') #Gets the API key for Google Gemini API

# The .env variables control how tier calculations are performed
GAMESPLAYED = os.getenv('gamesplayed') #Minimum games played to consider a higher tier
WINRATIO = os.getenv('winratio') #Winration needed to consider a higher tier
UNRANKED = os.getenv('unranked') #The remaining block sets the .env value of each rank's tier
IRON = os.getenv('iron')
BRONZE = os.getenv('bronze')
SILVER = os.getenv('silver')
GOLD = os.getenv('gold')
PLATINUM = os.getenv('platinum')
EMERALD = os.getenv('emerald')
DIAMOND = os.getenv('diamond')
MASTER = os.getenv('master')
GRANDMASTER = os.getenv('grandmaster')
CHALLENGER = os.getenv('challenger')

# Global variables set at startup and can be changed via commands
MAX_DEGREE_TIER = 2 #This number is used to determine how far apart in tiers players in opposing lanes can be during matchmaking
USE_RANDOM_SORT = True #This determines whether the player list is shuffled or sorted by tier 
USE_AI_MATCHMAKE = False #This determines whether team formation is done using AI or the Python methods
MIN_VOTES_REQUIRED = 3 #This is the minimum number of votes needed to declare an MVP winner
VOTE_DM = False #This determines whether voting is displayed in the channel or in player's DM

# Create credentials object for Google sheets
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Build the service object for Google sheets
service = build('sheets', 'v4', credentials=credentials)

# Set the Gemini AI API Key
genai.configure(api_key=GEMINI_API_KEY)

# on_ready event for script startup
@client.event
async def on_ready():
    # Assign global to changeable variables set at startup, can be changed via /settings command, this step is required
    global MAX_DEGREE_TIER
    MAX_DEGREE_TIER = MAX_DEGREE_TIER
    global USE_RANDOM_SORT
    USE_RANDOM_SORT = USE_RANDOM_SORT
    global USE_AI_MATCHMAKE
    USE_AI_MATCHMAKE = USE_AI_MATCHMAKE
    global VOTE_DM
    VOTE_DM = VOTE_DM
    global MIN_VOTES_REQUIRED
    MIN_VOTES_REQUIRED = MIN_VOTES_REQUIRED 

    check_database()
    await tree.sync(guild=discord.Object(GUILD))
    print(f'Logged in as {client.user}')


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
        ## Commented out the line outputting the change due to feedback that it generated too much noise
        # await interaction.response.send_message(f'Updated {self.values[0]} for {self.placeholder}', ephemeral=True)
        await interaction.response.defer(ephemeral=True)

#Button to set preferences to fill - embed did not have room so is unused currently
class FillButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Set to Fill", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        save_preference(interaction, "Fill - 44444")
        await interaction.response.send_message(f'Set preference to "Fill"', ephemeral=True)

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
            label = "Sit Out",
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
        sheets_export_points("Points_" + str(today.strftime('%m%d%Y')))
        await interaction.response.edit_message(view = self)
        await interaction.followup.send('Points data exported.', ephemeral=True)   
        
    @discord.ui.button(
            label = "Export Games",
            style = discord.ButtonStyle.green)
    async def export_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        sheets_export_games()
        await interaction.followup.send('Game data exported.', ephemeral=True)

    @discord.ui.button(
            label = "Export Rank History",
            style = discord.ButtonStyle.green)
    async def export_rankhistory(self, interaction: discord.Interaction, button: discord.ui.Button):
        today = datetime.now()
        sheets_export_playerrankhistory("RankHistory_" + str(today.strftime('%m%d%Y')))
        await interaction.response.edit_message(view = self)
        await interaction.followup.send('Rank history exported.', ephemeral=True)        

#endregion CLASSES


#region GENERAL METHODS

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
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Set the default message if no preferences are found (unlikely as a default is set at registration)
        pref = "No existing preferences, use the dropdowns to select:"

        # Query the player's preferences
        query = 'SELECT preferences FROM Player WHERE DiscordID = ?'
        args = (interaction.user.id,)
        cur.execute(query, args)
        result = cur.fetchone()

        # If preferences are found then create the string displaying them and return it
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
    # Position and preference are passed as a single string delimeted by a -
    position = value.split(" - ")[0]
    setpref = value.split(" - ")[1]

    # Get the Discord user that called the update
    member = interaction.user

    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Get the player's current preferences and save to the result param
        query = 'SELECT preferences FROM player WHERE discordID = ?'
        args = (member.id,)
        cur.execute(query, args)
        result = cur.fetchone()

        # Use the position to determine which preference is updated
        match position:
            # If this is called from the /fill command all preferences default to 4
            case "Fill":
                newpref = "44444"

            # For individual positions, the preference map is updated using the position and new preference joined to the existing preferences
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

        # Update the Player table with the new preference map
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
    # Get the discord ID of the user
    member = interaction.user
    
    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Check if the user's Discord ID exists yet
        query = 'SELECT EXISTS(SELECT discordName FROM player WHERE discordID = ?)'
        args = (member.id,)
        cur.execute(query, args)
        data = cur.fetchone()

        # If the ID does not exist a new entry will be inserted
        if data[0] == 0:
            # Create the insert - note the rank, tier, tier override, and preferences are set to a default instead of using nulls
            query = "INSERT INTO Player (discordID, discordName, riotID, lolRank, preferences, toxicity) VALUES (?, ?, '', 'unranked', '44444', 0)"
            args = (member.id, member.display_name,)
            cur.execute(query, args)
            dbconn.commit()

            # Returns an n/a for the Riot ID since this is a new user
            return "n/a"
        else:
            # If the user's Discord ID did exist then get their information from the database
            query = 'SELECT discordName, riotID FROM Player WHERE discordID = ?'
            args = (member.id,)
            cur.execute(query, args)
            result = cur.fetchone()

            # If the stored user name does not match the existing username then it will be updated automatically
            if member.display_name != result[0]:
                query = "UPDATE Player SET discordName = ? WHERE discordID = ?"
                args = (member.display_name, member.id,)
                cur.execute(query, args)
                dbconn.commit()                

            # Return the user's Riot ID to be displayed
            return str(result[1]).strip()

    except sqlite3.Error as e:
        print(f"Database error occurred registering player: {e}")

    finally:
        cur.close()
        dbconn.close()

#Method to create the database and objects if it is not found
def check_database():
    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # We're always going to drop and rebuild these objects using the .env file settings
        cur.execute("DROP VIEW IF EXISTS vw_TierModifier")
        cur.execute("DROP TABLE IF EXISTS TierMapping")

        # Triggers cannot be created with a IF NOT EXISTS so we will try to drop it and create it each run
        cur.execute("DROP TRIGGER IF EXISTS RankChangeTrigger")

        # Create a table to track if a user has voted for MVP in a certain game
        cur.execute("CREATE TABLE IF NOT EXISTS Voted (discordID bigint, gameID int);")

        # Clear data to keep the table trimmed
        cur.execute("DELETE FROM Voted;")

        # Create the tier mapping table
        cur.execute("CREATE TABLE TierMapping (lolRank varchar(64), tier int);")

        # Create the Player table
        cur.execute("""CREATE TABLE IF NOT EXISTS Player (
            discordID bigint PRIMARY KEY     	-- Unique Discord identifier for the player, will serve as PK
            , discordName nvarchar(64)			-- Player's Discord name
            , riotID nvarchar(64)				-- Player's LOL name
            , lolRank varchar(32)				-- Player's LOL rank
            , preferences varchar(512)			-- Player's encoded lane preferences (1H-5L) in order of Top, Jungle, Mid, ADC, and Support
            , toxicity int                      -- Player's toxicity score
            , tieroverride int                  -- Used by admins to override player's tier score, 0 uses calculated value
            );""")
        
        # Create the Games table
        cur.execute("""CREATE TABLE IF NOT EXISTS Games (
            gameID INTEGER PRIMARY KEY AUTOINCREMENT	    -- Unique ID to identify the game
            , gameDate date						-- Date of the game
            , gameNumber tinyint				-- Game number (1, 2, 3)	
            , gameLobby tinyint					-- Game Lobby (1, 2, 3) per 10 players
            , gameWinner varchar(4)				-- Team that won this game (Blue/Red)
            , isComplete bit                    -- Used to track incomplete games
            );""")

        # Create the GameDetail table
        cur.execute("""CREATE TABLE IF NOT EXISTS GameDetail (
            gameID int NOT NULL			-- Game ID joining back to the Games table
            , discordID bigint NOT NULL	-- Player ID joining back to the Player table
            , teamName varchar(32)		-- Team of the Player in this game ('Red', 'Blue', 'Participation')
            , gamePosition char(3)		-- Position played in this game (Top, Jng, Mid, ADC, Sup)
            , MVP bit					-- 0 = no MVP, 1 = MVP
            , FOREIGN KEY (gameID) REFERENCES Games (gameID)
            , FOREIGN KEY (discordID) REFERENCES Player (discordID)
            );""")
        
        # Create the RankHistory table
        cur.execute("""CREATE TABLE  IF NOT EXISTS RankHistory (
            discordID bigint        -- Player ID joining back to the Player table 
            , changedate date       -- Date the player's rank changed
            , oldrank varchar(64)   -- Player's old rank
            , newrank varchar(64)   -- Player's new rank
            , FOREIGN KEY (discordID) REFERENCES Player (discordID)
            );""")

        # Create the trigger to log when a player's rank changes
        cur.execute("""CREATE TRIGGER RankChangeTrigger
            AFTER UPDATE ON Player
            FOR EACH ROW
            BEGIN
                -- Insert the change into RankHistory table only if lolRank has been updated
                INSERT INTO RankHistory (discordID, changedate, oldrank, newrank)
                SELECT NEW.discordID, DATE('now'), OLD.lolRank, NEW.lolRank
                WHERE NEW.lolRank <> OLD.lolRank;
            END;""")

        # Create the view to calculate players' points
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

        # Create the view to calculate whether a player's performance should increase their rank
        cur.execute(f"""CREATE VIEW vw_TierModifier AS
            WITH totals AS (
            SELECT p.discordID 
                , SUM(CASE WHEN teamName = gameWinner THEN 1 ELSE 0 END) Wins
                , SUM(CASE WHEN teamName != 'Participation' THEN 1 ELSE 0 END) GamesPlayed
            FROM Player p
            INNER JOIN GameDetail gd ON gd.discordID = p.discordID
            INNER JOIN Games g ON g.gameID = gd.gameID
            WHERE g.gameDate >= (
                SELECT COALESCE((SELECT max(changedate) 
                FROM RankHistory 
                WHERE discordID = p.discordID), (SELECT min(gameDate) FROM Games)))
            GROUP BY p.discordID),

            winratio AS (
            SELECT t.discordID, Wins, GamesPlayed
                , CASE WHEN Wins = 0 OR GamesPlayed = 0 THEN 0 ELSE CAST(Wins AS float) / CAST(GamesPlayed AS float) END WinRatio
            FROM totals t
            INNER JOIN Player p ON p.discordID = t.discordID)

            SELECT discordID, CASE WHEN GamesPlayed >= {GAMESPLAYED} AND WinRatio >= {WINRATIO} THEN 1 ELSE 0 END tiermodifier
            FROM winratio
            """)

        # Create the player view that includes their tier calculation
        cur.execute("""CREATE VIEW IF NOT EXISTS vw_Player AS
            SELECT 
                CASE WHEN COALESCE(tieroverride,0) = 0 OR COALESCE(tieroverride,0) = '' 
				THEN tier - COALESCE(tiermodifier, 0)
                ELSE tieroverride
                END Tier
                , RiotID
                , Player.discordID
                , SUBSTRING(preferences, 1, 1) AS top_priority
                , SUBSTRING(preferences, 2, 1) AS jungle_priority
                , SUBSTRING(preferences, 3, 1) AS mid_priority
                , SUBSTRING(preferences, 4, 1) AS bot_priority
                , SUBSTRING(preferences, 5, 1) AS support_priority
            FROM Player
			INNER JOIN TierMapping tm ON lower(tm.lolrank) = lower(Player.lolRank)
			LEFT OUTER JOIN vw_TierModifier mod ON mod.discordID = Player.discordID""")

        # Finally insert the tier mapping data from .env
        cur.execute(f"""INSERT INTO TierMapping (lolRank, tier) VALUES ('unranked', {UNRANKED}),
            ('iron', {IRON}), ('bronze', {BRONZE}), ('silver', {SILVER}), ('gold', {GOLD}),
            ('platinum', {PLATINUM}), ('emerald', {EMERALD}), ('diamond', {DIAMOND}), ('master', {MASTER}),
            ('grandmaster', {GRANDMASTER}), ('challenger', {CHALLENGER})
            """)

        dbconn.commit()

        print ("Database is configured")

    except sqlite3.Error as e:
        print(f"Terminating due to database initialization error: {e}")
        exit()    

    finally:
        cur.close()
        dbconn.close()

#Method to add one toxicity point to the player
def update_toxicity(interaction, user):
    if "<@" in user:
        user = user[2:-1]

    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Var to determine if the user passed in exists
        found_user = False

        # Query to search for player by discordName or riotID
        query = 'SELECT EXISTS(SELECT discordName FROM player WHERE LOWER(discordName) = ? OR LOWER(riotID) = ? OR discordID = ?)'
        args = (user, user, user)
        cur.execute(query, args)
        data = cur.fetchone()

        # If the player is found we'll update them
        if data[0] != 0:
            # Set the return var to true since the user was found
            found_user = True

            # Create the update statement and add a point
            query = 'UPDATE Player SET toxicity = toxicity + 1 WHERE LOWER(discordName) = ? OR LOWER(riotID) = ? OR discordID = ?'
            args = (user, user, user)
            cur.execute(query, args)
            dbconn.commit()         

        return found_user
    except sqlite3.Error as e:
        print (f'Database error occurred updating toxicity: {e}')
        return e

    finally:
        cur.close()
        dbconn.close()
    
#Method to update Riot ID
def update_riotid(interaction: discord.Interaction, id):
    # Check that the ID looks correct and return a message if not
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

#Method to determine if the user is an admin
def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator

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

#Method for MVP voting called after a winning team is set
async def start_vote(interaction: discord.Interaction, gameID: int, winner: str, lobby: int):
    try:
        # Generate a table name using the unique gameID to store the votes temporarily
        votetable = f"Vote_{gameID}"

        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Just in case the table exists for some reason, drop it - note table names cannot be parameterized but gameID can only be an integer
        query = f'DROP TABLE IF EXISTS Vote_{gameID}'
        cur.execute(query)

        # Create the vote table
        query = f'CREATE TABLE Vote_{gameID} (gameID int, discordID varchar(128))'
        cur.execute(query)

        # This query will get the 10 players and their team name along with all participants for this game number from Lobby 1
        query = '''
            with gameplayers as (
            SELECT discordID, teamName
            FROM GameDetail
            WHERE gameID = ?
            UNION
            SELECT discordID, teamName
            FROM GameDetail
            WHERE gameID = 
                (SELECT g2.gameID 
                FROM Games g1 
                INNER JOIN Games g2 ON g2.gameDate = g1.gameDate 
                AND g2.gameNumber = g1.gameNumber
                AND g2.gameLobby = 1
                WHERE g1.gameID = ?)
            AND teamName = 'PARTICIPATION')

            SELECT gp.discordID, p.riotID, gp.teamName
            FROM gameplayers gp
            INNER JOIN Player p ON p.discordID = gp.discordID
        '''

        # Run the query and save the results to players
        cur.execute(query, [gameID, gameID])
        players = cur.fetchall()

        # Create the embed to notify voters
        embed = discord.Embed(title=f"MVP Vote - {winner} Team in Lobby #{lobby}", description=f"Vote for the MVP of the match by selecting their name below!", color=discord.Color.gold())

        # Create buttons for each player on the winning team by comparing the player's team to the winner param
        view = discord.ui.View()
        for player in players:
            if player[2] == winner:
                button = discord.ui.Button(label=player[1], custom_id=f'vote_{player[0]}', style=discord.ButtonStyle.success)

                # Create a button callback method for each button by passing the discordID, view, table name, gameID, and players list
                button.callback = create_vote_callback(player[0], view, votetable, gameID, players)

                # Add the button to the view
                view.add_item(button)

        # If the global parm for voting to be sent via DM is True then loop through the players and DM them
        if VOTE_DM:
            # Send the embed with voting buttons to each player privately in a DM
            for player in players:
                # Get the player's Discord ID
                user = await client.fetch_user(player[0])
                try:
                    # Send the message as a DM to each voting player
                    message = await user.send(embed=embed, view=view)
                    
                except discord.Forbidden:
                    # Handle the case where the player's DMs are closed
                    await client.send(f"Could not send a DM to {player[1]}. They may have DMs disabled.")
                    
        # Otherwise send the voting buttons to the channel and the callback will determine if they are allowed to vote
        else:
            message = await interaction.followup.send(embed=embed, view=view)

        # Start a 5-minute (300 seconds) timer for each user to vote
        await asyncio.sleep(300) 
        
        # After the time has elapsed the buttons will be disabled
        for item in view.children:
            item.disabled = True

        # Update the message to disable the buttons
        await message.edit(view=view)

        # At this point the voting period has ended so now we figure out the winner
        # Query the votetable to get the winner(s) - currently grants all ties an MVP score
        # The global MIN_VOTES_REQUIRED determines the minimum votes to allow a winner
        query = f"""
            WITH VoteCounts AS (
                SELECT discordID, COUNT(*) AS VoteCount
                FROM {votetable}
                GROUP BY discordID),
            MaxVotes AS (
                SELECT MAX(VoteCount) AS MaxVoteCount
                FROM VoteCounts
                WHERE VoteCount >= ?)

            SELECT vc.discordID, p.riotID
            FROM VoteCounts vc
            INNER JOIN Player p ON p.discordID = vc.discordID
            WHERE VoteCount = (SELECT MaxVoteCount FROM MaxVotes);
            """
        
        # Execute the query and save the results to mvplist
        cur.execute(query, [MIN_VOTES_REQUIRED])
        mvplist = cur.fetchall()

        # Make sure someone won MVP, if not create an embed announce no winner was chosen
        if len(mvplist) == 0:
            mvpembed = discord.Embed(title=f"MVP Winner - {winner} Team in Lobby #{lobby}", description=f"No player won MVP this round!", color=discord.Color.gold())

        else:
            # Create the embed to display the voted winner(s)
            mvpembed = discord.Embed(title=f"MVP Winner - {winner} Team in Lobby #{lobby}", description=f"Here are the MVP(s) for this game!", color=discord.Color.gold())

            # Update the GameDetail table with each of the MVPs
            for mvp in mvplist:
                query = "UPDATE GameDetail SET MVP = 1 WHERE gameID = ? AND discordID = ?;"
                cur.execute(query, [gameID, mvp[0]])
                dbconn.commit()

                # Add the name to the embed
                mvpembed.add_field(name=mvp[1], value=f"\u200B")

        # Now that voting is complete the table can be dropped
        query = f"DROP TABLE IF EXISTS {votetable};"
        cur.execute(query)

        # Send a message to the channel to display MVP winner(s)
        await interaction.followup.send(embed=mvpembed)

    except sqlite3.Error as e:
        print(f"Terminating due to database MVP voting error: {e}")
        return False
    
    finally:
        cur.close()
        dbconn.close() 
        return    

#Method that serves as a callback from the voting buttons
def create_vote_callback(discord_id, view, votetable, gameId, players):
    async def vote_callback(interaction):
        try:
            # Create the database connection
            dbconn = sqlite3.connect("bot.db")
            cur = dbconn.cursor()

            # First check if we are using DM voting, if not then we need to check that this user is a valid voter
            if not VOTE_DM:
                # Default to False for the user being allowed to vote
                allowed_vote = False

                # Loop through the players list that was sent
                for player in players:
                    # If the user who clicked the button is in the list then the allowed vote is set to True
                    if interaction.user.id == player[0]:
                        allowed_vote = True

                # After the loop, if the user was not set to be allowed to vote a message will be sent and the callback ends
                if not allowed_vote:
                    # Inform the user they cannot vote                
                    await interaction.response.send_message("Sorry, you are not allowed to vote for this match.", ephemeral=True)
                    return

                # Now check to make sure the user has not already voted by checking their ID and gameID against the Voted table
                cur.execute("SELECT EXISTS(SELECT discordID from Voted WHERE discordID = ? AND gameID = ?)", [interaction.user.id, gameId])
                hasvoted = cur.fetchone()

                # If the user's ID exists then they have already voted and the callback ends
                if hasvoted[0] == 1:
                    # Inform the user they cannot vote                
                    await interaction.response.send_message("Sorry, you already voted for this match.", ephemeral=True)
                    return

            # At this point the user is valid and has not previously voted

            # Use the values passed by the button click and insert the vote into the table
            query = f"INSERT INTO {votetable} VALUES (?, ?)"
            cur.execute(query, [gameId, discord_id])
            dbconn.commit()

            # If using DM voting, disable all buttons in the view after a vote is submitted (no double voting)
            if VOTE_DM:
                for item in view.children:
                    item.disabled = True

            # If voting in the channel we cannot disable the buttons so we will track the user's vote
            else:
                query = f"INSERT INTO Voted VALUES (?, ?)"
                cur.execute(query, [interaction.user.id, gameId])
                dbconn.commit()

            # Update the message to disable the buttons
            await interaction.message.edit(view=view)
            
            # Notify the user their vote has been recorded
            await interaction.response.send_message("Thank you for your vote!", ephemeral=True)

        except sqlite3.Error as e:
            print(f"Terminating due to database MVP voting error: {e}")
            return False

        finally:
            cur.close()
            dbconn.close() 

    # End the callback
    return vote_callback

#Method returns how many volunteers are needed to make the players a divisible amount of 10
def count_volunteers_needed(interaction):
    #Finds all players in discord, adds them to a list
    player_role = get(interaction.guild.roles, name='Player')
    player_users = [member.id for member in player_role.members]

    # If there at least 10 players and they are not divisible by 10 then return the number
    if len(player_users) % 10 != 0 and len(player_users) >= 10:
        additional_volunteers_needed = (len(player_users) % 10)

    # If the condition isn't true then no volunteers are needed
    else:
        additional_volunteers_needed = 0
    
    # Return the number
    return additional_volunteers_needed

#endregion GENERAL METHODS

#region MATCHMAKING METHODS

#Method to assign roles to players based on their preferred priority
def assign_roles(players):
    # Create an array of the possible roles
    roles = ['top', 'jungle', 'mid', 'bot', 'support']

    # Create a priority map for the player's preferences
    priority_mapping = {1: [], 2: [], 3: [], 4: [], 5: []}

    # Loop through each player and map their preferences for each lane
    for player in players:
        for idx, priority in enumerate([player.top_priority, player.jungle_priority, player.mid_priority, player.bot_priority, player.support_priority]):
            priority_mapping[int(priority)].append((player, roles[idx]))
    
    # Create the array for the role assignments
    role_assignments = {}

    # Create the list of players that have been assigned
    assigned_players = set()
    
    # Sort by the lane priority and loop through assigning players to their most desired lanes first
    for priority in sorted(priority_mapping.keys()):
        for player, role in priority_mapping[priority]:
            if role not in role_assignments and player not in assigned_players:
                role_assignments[role] = player
                assigned_players.add(player)
    
    # Return the role assignments
    return role_assignments

#Method that validates players are within <degree> tier of each other and returns true or false
def validate_team_matchup(red_team, blue_team, degree):
    # Create an array of the possible roles
    roles = ['top_laner', 'jungle', 'mid_laner', 'bot_laner', 'support']
    
    # Loop through each role
    for role in roles:
        # Assign the player for this role for each team
        red_player = getattr(red_team, role)
        blue_player = getattr(blue_team, role)

        # Compare the difference between the tier, if not within the allowed degree return a false
        if abs(red_player.tier - blue_player.tier) > degree:
            return False
        
    # At this point the validation has passed and true is returned
    return True

#Method to create and return a balanced team
def find_balanced_teams(players, degree):
    # itertools will form a list of every possible combination of the 10 players divided into 2 teams
    possible_combinations = itertools.combinations(players, len(players) // 2)

    # Loop through every possible combination
    for combination in possible_combinations:
        # First assign the combination of players to the red team
        red_team_players = list(combination)

        # Next assign the remaining players not in red to the blue team
        blue_team_players = [player for player in players if player not in red_team_players]
        
        # Next call the role assignment for both sets of players
        red_team_roles = assign_roles(red_team_players)
        blue_team_roles = assign_roles(blue_team_players)

        # Create the team class for red and blue
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

        # Call this method to validate the tier difference of opposing lanes are within the degree threshold and return the teams if true
        if validate_team_matchup(red_team, blue_team, degree):
            return red_team, blue_team

    # If the code gets here there is no possible combination of players that meets the tier difference
    return None, None

#Method to create balanced teams using the MAX_DEGREE_TIER and USE_AI_MATCHMAKE to manipulate the results
def balance_teams(players):
    # If the USE_AI_MATCHMAKE is set to true the code will use Gemini to form the teams
    if USE_AI_MATCHMAKE:
        # Attempt to form teams by calling the Gemini method
        red_team, blue_team = gemini_ai_find_teams(players)
        
        # If either team did not form this will return none
        if red_team is None or blue_team is None:
            return None, None
    
    # Otherwise teams will be created using the python methods
    else:
        # Attempt to create two teams with a degree of tier difference starting at 0 for the most balanced team possible
        red_team, blue_team = find_balanced_teams(players, 0)
        
        # Set # of attempts to 1
        attempts = 1

        # Begin a loop to run while either team is still not formed
        while red_team is None or blue_team is None:
            # Check to see if the number of attempts has met or exceeded the max degree setting and return none if true
            if attempts > MAX_DEGREE_TIER and (red_team is None or blue_team is None):
                return None, None    

            # Each iteration of the loop will try again with each iteration adding one more degree of separation between opposing lanes
            red_team, blue_team = find_balanced_teams(players, attempts)

            # Increment the attempts counter
            attempts += 1

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

#Method to take users in the player role and pull their preferences to pass to the balance_teams method
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

#endregion MATCHMAKING METHODS

# region GOOGLE SHEETS

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

#Method to export the player's rank change
def sheets_export_playerrankhistory(sheet_name):
    # First check if the sheet exists yet, if yes clear it out
    sheets_create(sheet_name, True)

    try:
        # Create the database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Query to get the information from the player table
        query = "SELECT * FROM RankHistory"
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

#endregion GOOGLE SHEETS


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
    # Check if the player is an admin and end if they are not
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    
    
    # Create the check in class and send the view to the channel
    view = CheckinButtons(timeout=timeout)
    await interaction.response.send_message(f'Check-In for the tournament has started! You have {timeout//60} minutes to check-in.', view = view)

#Command to set preferences to fill (44444 is used)
@tree.command(
        name = 'fill',
        description= 'Set your position preferences to fill.',
        guild = discord.Object(GUILD))
async def fill(interaction):
    # Register the player to make sure they have been added to the database
    register_player(interaction)

    # Use the save preference function and pass the fill param to set everything to 4
    save_preference(interaction, "Fill - 44444")
    await interaction.response.send_message("Your preference has been set to fill", ephemeral=True)

#Command to update position preferences
@tree.command(
        name = 'roleselect',
        description= 'Update your role preferences.',
        guild = discord.Object(GUILD))
async def roleselect(interaction):
    # Make sure the player has been created
    register_player(interaction)

    # Create the embed showing current preferences 
    embed = discord.Embed(title="Select your role preferences (1 (high) to 5 (never))", 
                          description=get_preferences(interaction), color=0x00ff00)
    
    # Create the drop down list view for selecting preferences and display it
    view = PreferenceDropdownView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

#Command to start volunteer
@tree.command(
    name = 'volunteer',
    description = 'initiate check for volunteers',
    guild = discord.Object(GUILD))
async def volunteer(interaction):
    # Check if the player is an admin and end if they are not
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    
    
    # Call the count function to determine how many volunteers are needed to have an even 10 divisible Player count
    volunteers_needed = count_volunteers_needed(interaction)

    # If no volunteers are needed output a message and end the call
    if volunteers_needed == 0:
        await interaction.response.send_message('No volunteers are needed.', ephemeral=True)
        return
    
    # If volunteers are needed then create the view and send it to the channel along with the count of how many are needed
    else:
        view = volunteerButtons()

        # Defer the response, because of the channel.send there will be two messages in the channel so we must handle both
        await interaction.response.defer()

        # channel.send is used here because response and followup did not return the message context which is needed to remove the volunteer embed
        message = await interaction.channel.send(f'The Volunteer check has started! {volunteers_needed} volunteers needed to sit out .', view = view)

    # Keep checking if volunteers are needed
    while volunteers_needed != 0:
        # Wait 1 second to check, this is not super intensive and helps end the embed as soon as the last volunteer clicks
        await asyncio.sleep(1)

        # Get the count again
        volunteers_needed = count_volunteers_needed(interaction)

    # Once enough volunteers have signed up delete the volunteer embed
    await message.delete()

    # Follow up on the original message and post that there are no more volunteers needed
    await interaction.followup.send('Volunteer check completed! No more volunteers needed.')

# Command to add a point of toxicity to a player
@tree.command(
        name = 'toxicity',
        description = 'Give a user a point of toxicity, you can use @Discord name, nickname, or Riot ID.',
        guild = discord.Object(GUILD))
async def toxicity(interaction: discord.Interaction, username: str):
    # Check if the player is an admin and end if not
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    try:
        # Call the method to update the database and check if it returns a success
        found_user = update_toxicity(interaction, username.lower())
        if found_user:
            await interaction.response.send_message(f"{username}'s toxicity point has been updated.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{username} could not be found.", ephemeral=True)

    except Exception as e:
        print(f'An error occured: {e}')

#Slash command to remove all users from the Player and Volunteer role.
@tree.command(
    name = 'clear',
    description = 'Remove all users from Players and Volunteer roles.',
    guild = discord.Object(GUILD))
async def remove(interaction: discord.Interaction):
    # Check if the player is an admin and end if not
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    

    try:
        # Grab the player and volunteer roles
        player = get(interaction.guild.roles, name = 'Player')
        volunteer = get(interaction.guild.roles, name = 'Volunteer')
        
        # This may not be necessary as it runs very quickly, but this was part of the original bot
        await interaction.response.defer(ephemeral = True)
        await asyncio.sleep(1)

        # Loop through the users in the channel and remove them from either role they exist in
        for user in interaction.guild.members:
            if player in user.roles:
                await user.remove_roles(player)
            if volunteer in user.roles:
                await user.remove_roles(volunteer)

        # Send a followup message that the roles are cleared
        await interaction.followup.send('All users have been removed from roles.')

    except Exception as e:
        print(f'An error occured: {e}')

#Slash command to find and count all of the players and volunteers
@tree.command(
        name='players',
        description='Find all players and volunteers currently enrolled in the game',
        guild = discord.Object(GUILD))
async def players(interaction: discord.Interaction):
    # Check if the player is an admin and end if not
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    # Create an empty message var for appending the final message
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

        # Create a count of each role
        player_count = sum(1 for user in interaction.guild.members if player in user.roles)
        volunteer_count = sum(1 for user in interaction.guild.members if volunteer in user.roles)

        # Embed to display users in the Player role
        embedPlayers = discord.Embed(color = discord.Color.green(), title = 'Total Players')
        embedPlayers.set_footer(text = f'Total players: {player_count}')
        for pl in player_users:
            embedPlayers.add_field(name = '', value = pl)

        #Embed to display all users who volunteered to sit out.
        embedVolunteers = discord.Embed(color = discord.Color.orange(), title = 'Total Volunteers')
        embedVolunteers.set_footer(text = f'Total volunteers: {volunteer_count}')
        for vol in volunteer_users:
            embedVolunteers.add_field(name = '', value = vol)
        
        # Use the counts to determine the correct output, whether the lobby is good, needs more players, or needs volunteers
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
    description = "Form teams. Pass a match_number of the next match for the day.",
    guild = discord.Object(GUILD))
async def matchmake(interaction: discord.Interaction, match_number: int, reroll: bool = False):
    # Check if the player is an admin and end if not
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

        # Query to check if the match number has been used already today
        query = "SELECT EXISTS (SELECT * FROM Games WHERE gameNumber = ? and gameDate = DATE('now'))"
        cur.execute(query, [match_number,])
        result = cur.fetchone()

        # First check if the game already exists AND the admin wants to reroll the existing team
        if result[0] != 0 and reroll:
            # If true then erase the game from the database and continue matchmaking
            reset_db_match(match_number)

        # If EXISTS does not return a 0 and there's no reroll then the given match number has already been used today and the method ends
        elif result[0] != 0:
            await interaction.response.send_message(f'Match number {match_number} has already been used today', ephemeral = True)
            print("Matchmake command called using a match number that was already used for today.")
            return

        # Query to make sure no games have been left active, this ensures the win command is used after games are played
        query = "SELECT EXISTS (SELECT * FROM Games WHERE isComplete = 0)"
        cur.execute(query)
        result = cur.fetchone()

        # If EXISTS does not return a 0 there are games that have not been closed and the method ends
        if result[0] != 0:
            await interaction.response.send_message('There are one or more incomplete games that need to be closed, see /activegames', ephemeral = True)
            print("Matchmake command called with incomplete games still active.")
            return

        #Finds all players in discord, adds them to a list
        player_role = get(interaction.guild.roles, name='Player')
        player_users = [member.id for member in player_role.members]

        #Finds all volunteers in discord, adds them to a list.  _users is used for the embed out and _ids is used for the database
        volunteer_role = get(interaction.guild.roles, name='Volunteer')
        volunteer_users = [member.name for member in volunteer_role.members]
        volunteer_ids = [member.id for member in volunteer_role.members]

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
            # Because idx corresponds to Lobby# and the array is 0 based, subtract 1 from the current index
            blueteam, redteam = balance_teams(player_list[idx-1])

            # If either team did not get created no possible combination was found with the current setting
            if blueteam is None or redteam is None:
                reset_db_match(match_number)
                
                # Response type will depend on whether AI is used - with defer this will not be ephemeral
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
                embedLobby1.add_field(name = '', value = 'Top')
                embedLobby1.add_field(name = '', value = blueteam.top_laner.username)
                embedLobby1.add_field(name = '', value = redteam.top_laner.username)
                embedLobby1.add_field(name = '', value = 'Jungle')
                embedLobby1.add_field(name = '', value = blueteam.jungle.username)
                embedLobby1.add_field(name = '', value = redteam.jungle.username)
                embedLobby1.add_field(name = '', value = 'Mid')
                embedLobby1.add_field(name = '', value = blueteam.mid_laner.username)
                embedLobby1.add_field(name = '', value = redteam.mid_laner.username)
                embedLobby1.add_field(name = '', value = 'Bot')
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
    )
async def win(interaction: discord.Interaction, lobby: int, winner: str):
    # Check if the player is an admin and end if not
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return    
    
    try:
        # Create database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Create query to check if the passed Lobby # is a valid open game by getting the gameID
        query = 'SELECT gameID FROM Games WHERE isComplete = 0 AND gameLobby = ?'
        cur.execute(query, [lobby])
        gameID = cur.fetchone()

        # If the EXISTS returns a 0 then there is no active game for the lobby provided and the method ends
        if gameID is None:
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
        await start_vote(interaction, gameID[0], winner.upper(), lobby)

#Slash command to see active games
@tree.command(
    name = 'activegames',
    description = "Shows all games that have not been closed with /win",
    guild = discord.Object(GUILD))
async def activegames(interaction: discord.Interaction):
    # Check if the player is an admin and end if not
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
        await interaction.response.send_message(embed = embedGames, ephemeral=True)
        
    # Catch sql errors, print to console and output message to Discord
    except sqlite3.Error as e:
        print(f"Terminating due to database active games error: {e}")
        await interaction.response.send_message(f"Failed due to database error {e}", ephemeral=True)

    finally:
        cur.close()
        dbconn.close() 

#Command to display the export embed with buttons for exporting the database to Sheets
@tree.command(
        name = 'export',
        description= 'Export database to Google sheets.',
        guild = discord.Object(GUILD))
async def export(interaction):
    # Check if the player is an admin and end if not
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    # Create the view and display it
    view = ExportButtons()
    await interaction.response.send_message(f'Use the buttons below to export the database to Google sheets', view = view, ephemeral=True)

#Slash command to see and change admin settings
@tree.command(
    name = 'settings',
    description = "View and/or change global settings.  Each paramter is optional.",
    guild = discord.Object(GUILD))
async def settings(interaction: discord.Interaction, use_ai: str = '', random_sort: str = '', max_tier: int = -1, min_votes: int = -1, vote_dm: str = ''):
    # This seemed to take longer than expected in testing so better to defer
    await interaction.response.defer(ephemeral=True)
    
    # This is an admin only command so check and bounce if not an admin
    if not is_admin(interaction):
        await interaction.followup.send("This command is only for administrators.", ephemeral=True)
        return
    
    # All params are options, if the AI value isn't blank AND it is true or false then it will change the global param
    if use_ai != '' and (use_ai.lower() == 'true' or use_ai.lower() == 'false'):
        # If true then set it to true
        if use_ai.lower() == 'true':
            global USE_AI_MATCHMAKE
            USE_AI_MATCHMAKE = True

        # Otherwise it had to be false
        else:
            USE_AI_MATCHMAKE = False

        # Display the change 
        await interaction.followup.send(f"USE_AI_MATCHMAKE has been set to {USE_AI_MATCHMAKE}", ephemeral=True)

    # Same setup as AI above
    if random_sort != '' and (random_sort.lower() == 'true' or random_sort.lower() == 'false'):
        # If true then set it to true
        if random_sort.lower() == 'true':
            global USE_RANDOM_SORT
            USE_RANDOM_SORT = True
        
        # Otherwise it had to be false
        else:
            USE_RANDOM_SORT = False

        # Display the change 
        await interaction.followup.send(f"USE_RANDOM_SORT has been set to {USE_RANDOM_SORT}", ephemeral=True)

    # Same setup as AI above
    if vote_dm != '' and (vote_dm.lower() == 'true' or vote_dm.lower() == 'false'):
        # If true then set it to true
        if vote_dm.lower() == 'true':
            global VOTE_DM
            VOTE_DM = True
        
        # Otherwise it had to be false
        else:
            VOTE_DM = False

        # Display the change 
        await interaction.followup.send(f"VOTE_DM has been set to {VOTE_DM}", ephemeral=True)

    # Same premise although this is an integer value instead of true/false
    if max_tier >= 0 and isinstance(max_tier, int):
        # If this is a valid number assign it
        global MAX_DEGREE_TIER
        MAX_DEGREE_TIER = max_tier

        # Display the change 
        await interaction.followup.send(f"MAX_DEGREE_TIER has been set to {MAX_DEGREE_TIER}", ephemeral=True)

    # Same premise although this is an integer value instead of true/false
    if min_votes >= 0 and isinstance(min_votes, int):
        # If this is a valid number assign it
        global MIN_VOTES_REQUIRED
        MIN_VOTES_REQUIRED = min_votes

        # Display the change 
        await interaction.followup.send(f"MIN_VOTES_REQUIRED has been set to {MIN_VOTES_REQUIRED}", ephemeral=True)

    # If no param was changed then simply display the param values
    # Create the embed for displaying the game information, will show 0 if no games are returned
    embedGames = discord.Embed(color = discord.Color.green(), title = 'Bot Settings')

    # Loop the data returned and add a line for each active game to the embed
    embedGames.add_field(name = 'USE_AI_MATCHMAKE', value = f"{USE_AI_MATCHMAKE}", inline=False)
    embedGames.add_field(name = 'MAX_DEGREE_TIER', value = f"{MAX_DEGREE_TIER}", inline=False)
    embedGames.add_field(name = 'USE_RANDOM_SORT', value = f"{USE_RANDOM_SORT}", inline=False)
    embedGames.add_field(name = 'VOTE_DM', value = f"{VOTE_DM}", inline=False)
    embedGames.add_field(name = 'MIN_VOTES_REQUIRED', value = f"{MIN_VOTES_REQUIRED}", inline=False)

    # Output the embed
    await interaction.followup.send(embed = embedGames, ephemeral=True)

# Slash command to quickly see a user's info from the database
@tree.command(
    name = 'showuser',
    description = "Display information for a specified user.",
    guild = discord.Object(GUILD))
async def showuser(interaction: discord.Interaction, username: str):
    # Admin only command
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return

    try:
        # If the user was passed in using the @Discordname parse the ID
        if "<@" in username:
            username = username[2:-1]

        # Create database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Search for the player by Riot ID or by their Discord Name
        query = f"""
            SELECT discordName, p.riotID, lolRank, toxicity, Tier, tieroverride
            FROM Player p
            INNER JOIN vw_Player vp ON vp.discordID = p.discordID
            WHERE LOWER(discordName) = ? OR LOWER(p.riotID) = ? or p.discordID = ?
            """
        cur.execute(query, [username.lower(), username.lower(), username])
        player = cur.fetchone()

        # If the player is not found then return a message
        if player == None:
            await interaction.response.send_message(f"{username} was not found in the database.", ephemeral=True)
        
        else:
            # Create the embed for displaying the player information
            embedPlayer = discord.Embed(color = discord.Color.green(), title = 'Player Results: ' + username)

            # Loop the data returned and add a line for each active game to the embed
            embedPlayer.add_field(name = 'Discord Name', value = player[0], inline=False)
            embedPlayer.add_field(name = 'Riot ID', value = player[1], inline=False)
            embedPlayer.add_field(name = 'League Rank', value = player[2], inline=False)
            embedPlayer.add_field(name = 'Toxicity', value = player[3], inline=False)
            embedPlayer.add_field(name = 'Calculated Tier', value = player[4], inline=False)
            embedPlayer.add_field(name = 'Tier Override Value (Overrides Calculated Value)', value = player[5], inline=False)

            # Output the embed
            await interaction.response.send_message(embed = embedPlayer, ephemeral=True)

    # Catch sql errors, print to console and output message to Discord
    except sqlite3.Error as e:
        print(f"Terminating due to database show user error: {e}")

    finally:
        cur.close()
        dbconn.close() 
        return

#Slash command to delete all game data while preserving user data
@tree.command(
    name = 'cleargamedata',
    description = "Clears the game data from the database, enter I KNOW WHAT I AM DOING (all caps) to proceed.",
    guild = discord.Object(GUILD))
async def cleargamedata(interaction: discord.Interaction, reassurance: str):
    # Check if the user is the owner of the guild/channel
    if interaction.user.id != interaction.guild.owner.id:
        await interaction.response.send_message("This command is only for the guild owner.", ephemeral=True)
        return
    
    # Case sensitive - check that the user really intends to do this
    if reassurance == "I KNOW WHAT I AM DOING":
        # Create a backup copy of the database in the event of an OOPSIE DOODLES
        shutil.copyfile("bot.db", "BACKUP_bot_" + time.strftime("%Y%m%d-%H%M%S") + ".db")

        try:
            # Create database connection
            dbconn = sqlite3.connect("bot.db")
            cur = dbconn.cursor()

            # Delete all the game detail data
            query = f"DELETE FROM GameDetail;"
            cur.execute(query)
            dbconn.commit()

            # Delete the game data
            query = f"DELETE FROM Games;"
            cur.execute(query)
            dbconn.commit()        

            # Reset the GameID sequence
            query = f"DELETE FROM sqlite_sequence where name='Games';"
            cur.execute(query)
            dbconn.commit()             

            # Reset all player's toxicity
            query = f"UPDATE Player SET toxicity = 0;"
            cur.execute(query)
            dbconn.commit()    

            # Output the embed
            await interaction.response.send_message("Game data has been removed and a backup database was created.", ephemeral=True)
            
        # Catch sql errors, print to console and output message to Discord
        except sqlite3.Error as e:
            print(f"Terminating due to database clear error: {e}")
            await interaction.response.send_message(f"Failed due to database error {e}", ephemeral=True)

        finally:
            cur.close()
            dbconn.close() 
            return
        
    else:
        await interaction.response.send_message("Data not purged.  Use the phrase I KNOW WHAT I AM DOING in all caps if you wish to continue.", ephemeral=True)

#Slash command to delete all game data while preserving user data
@tree.command(
    name = 'setplayertier',
    description = "Set a player's tier to override their calculated tier.",
    guild = discord.Object(GUILD))
async def setplayertier(interaction: discord.Interaction, username: str, tier: int):
    # Admin only command
    if not is_admin(interaction):
        await interaction.response.send_message("This command is only for administrators.", ephemeral=True)
        return
    
    try:
        # If the user was passed in using the @Discordname parse the ID
        if "<@" in username:
            username = username[2:-1]
    
        # Create database connection
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        # Search for the player by Riot ID or by their Discord Name
        query = f"""
            SELECT discordName, Tier, tieroverride
            FROM Player p
            INNER JOIN vw_Player vp ON vp.discordID = p.discordID
            WHERE LOWER(discordName) = ? OR LOWER(p.riotID) = ? OR p.discordID = ?
            """
        cur.execute(query, [username.lower(), username.lower(), username])
        player = cur.fetchone()

        # If the player is not found then return a message
        if player == None:
            await interaction.response.send_message(f"{username} was not found in the database.", ephemeral=True)
        
        else:
            # Query to save the change
            query = """
                UPDATE PLAYER SET tieroverride = ?
                WHERE LOWER(discordName) = ? OR LOWER(riotID) = ? OR discordID = ?
                """
            cur.execute(query, [tier, username.lower(), username.lower(), username])
            dbconn.commit()

            # Create the embed for displaying the change
            embedTier = discord.Embed(color = discord.Color.green(), title = 'Player Tier: ' + username)
            embedTier.add_field(name = 'Old override tier', value = player[2], inline=False)
            embedTier.add_field(name = 'Old calculated tier', value = player[1], inline=False)
            embedTier.add_field(name = 'New override tier', value = tier, inline=False)

            # Output the embed
            await interaction.response.send_message(embed=embedTier, ephemeral=True)
        
    # Catch sql errors, print to console and output message to Discord
    except sqlite3.Error as e:
        print(f"Terminating due to database clear error: {e}")
        await interaction.response.send_message(f"Failed due to database error {e}", ephemeral=True)

    finally:
        cur.close()
        dbconn.close() 
        return



#endregion COMMANDS

#starts the bot
client.run(TOKEN)
