import asyncio
import discord
import os
import itertools
import logging
import gspread
# from oauth2client.service_account import ServiceAccountCredentials
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv, find_dotenv
from discord import app_commands
from discord.utils import get
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from discord.ext import commands
import sqlite3
import random
from operator import itemgetter

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
    def __init__(self, *, timeout = 900):
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
            );""")
        
        cur.execute("""CREATE TABLE IF NOT EXISTS Games (
            gameID bigint PRIMARY KEY		    -- Unique ID to identify the game
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

#Method to create teams
def create_teams(self, player_users):
    # matched_players = []

    # Player definition order = self, tier, username, discord_id, top_priority, jungle_priority, mid_priority, bot_priority, support_priority
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        query = f"SELECT * FROM Player WHERE discordID IN ({','.join(['?' for _ in player_users])})"
        cur.execute(query, player_users)
        data = cur.fetchall()

        # for pl in data:
        #     matched_players.append(Player(self, pl[3], pl[2], pl[1], pl[4][0], pl[4][1], pl[4][2], pl[4][3], pl[4][4]))
            
    except sqlite3.Error as e:
        print (f'Database error occurred creating teams: {e}')
        return e

    finally:
        cur.close()
        dbconn.close()    

    # for i, row in enumerate(values):
    #     for player in player_users:
    #         if player.lower() == row[0].lower():
    #             top_prio = 5
    #             jg_prio = 5
    #             mid_prio = 5
    #             bot_prio = 5
    #             supp_prio = 5
    #             if row[3] == 'fill':
    #                 top_prio = 1
    #                 jg_prio = 1
    #                 mid_prio = 1
    #                 bot_prio = 1
    #                 supp_prio = 1
    #             roles = row[3].split('/')
    #             index = 1
    #             for i, role in enumerate(roles):
    #                 if role.lower() == 'top':
    #                     top_prio = index
    #                 if role.lower() == 'jg' or role.lower() == 'jung' or role.lower() == 'jungle':
    #                     jg_prio = index
    #                 if role.lower() == 'mid':
    #                     mid_prio = index
    #                 if role.lower() == 'bot' or role.lower() == 'adc':
    #                     bot_prio = index
    #                 if role.lower() == 'supp' or role.lower() == 'support':
    #                     supp_prio = index
    #                 index += 1
    #             matched_players.append(Player(tier=row[4],username=row[1],discord_id=row[0], top_priority=top_prio, jungle_priority=jg_prio, mid_priority=mid_prio, bot_priority=bot_prio, support_priority=supp_prio))    
    return

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


def assign_roles(players):
    position_map = ["Top", "Jungle", "Mid", "ADC", "Support"]
    positions = {position: [] for position in position_map}
    
    for player in players:
        preferences = list(player[2])
        for i, pos in enumerate(position_map):
            positions[pos].append((player, int(preferences[i])))

    for pos in positions:
        positions[pos] = sorted(positions[pos], key=itemgetter(1))
    
    return positions


def balanced_teams(players):
    positions = assign_roles(players)
    team_red = {}
    team_blue = {}

    for position, candidates in positions.items():
        for candidate in candidates:
            player = candidate[0]
            if player[0] in team_red.values():
                continue
            if player[0] in team_blue.values():
                continue

            if position in team_red:
                team_blue[position] = player[0]
            else:
                team_red[position] = player[0]

    return team_red, team_blue


def check_balance(team_red, team_blue, players):
    rank_order = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Emerald', 'Diamond', 'Master', 'Grandmaster', 'Challenger']
    position_map = ["Top", "Jungle", "Mid", "ADC", "Support"]

    player_ranks = {player[0]: player[1] for player in players}
    
    for position in position_map:
        red_rank = player_ranks[team_red[position]]
        blue_rank = player_ranks[team_blue[position]]
        if abs(rank_order.index(red_rank) - rank_order.index(blue_rank)) > 1:
            return False
    return True


def create_teams(players):
    team_red, team_blue = balanced_teams(players)
    while not check_balance(team_red, team_blue, players):
        random.shuffle(players)
        team_red, team_blue = balanced_teams(players)
    
    return team_red, team_blue


#endregion METHODS



#region COMMANDS

#Command to update player's league of legends ID
@tree.command(
    name = 'riotid',
    description = 'Update your Riot ID <Game Name><#Tagline>',
    guild = discord.Object(GUILD))
async def riotid(interaction, id: str):
    update_riotid(interaction, id)
    await interaction.response.send_message(f'Your League of Legends ID has been updated to {id}.', ephemeral=True)

#Command to start check-in
@tree.command(
    name = 'checkin',
    description = 'Initiate Tournament Check-In.  Add timeout in seconds or use the default of 900 - 15 minutes.',
    guild = discord.Object(GUILD))
async def checkin(interaction, timeout: int=900):
    view = CheckinButtons(timeout)
    await interaction.response.send_message('Check-In for the tournament has started! You have 15 minutes to check-in.', view = view)

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
    embed = discord.Embed(title="Select your role preferences", 
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

@tree.command(
    name = 'matchmake',
    description = "Form teams for all players enrolled in the game.",
    guild = discord.Object(GUILD))
async def matchmake(interaction: discord.Interaction, match_number: int):
    try:
        #Finds all players in discord, adds them to a list
        player_role = get(interaction.guild.roles, name='Player')
        player_users = [member.id for member in player_role.members]

        #Finds all volunteers in discord, adds them to a list
        volunteer_role = get(interaction.guild.roles, name='Volunteer')
        volunteer_users = [member.id for member in volunteer_role.members]

        # Check for player count % 10 = 0
        # If > 10 players, sort players by rank
        # Set lobby count = player count / 10
        # Iterate lobby count, create both teams

        if len(player_users) % 10 != 0:
            await interaction.followup.send('There is not a multiple of 10 players, please see /players', ephemeral = True)
            return

        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()
        query = "SELECT EXISTS (SELECT * FROM Games WHERE isComplete = 0)"
        result = cur.execute(query)

        if result[0] != 0:
            await interaction.followup.send('There are one or more incomplete games that need to be closed, see /activegames', ephemeral = True)
            return

        for idx in range(0, player_users.count()/10):
            query = "INSERT INTO Games (gameDate, gameNumber, gameLobby, isComplete) VALUES (GETDATE(), ?, ?, 0)"
            args = (match_number, idx,)
            cur.execute(query, args)
            dbconn.commit()

    except Exception as e:
        print(f'An error occured: {e}')



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
