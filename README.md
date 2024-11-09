
# KSU Capstone Project Fall 2024


Project is to create a Discord bot that can perform administrative procedures for running a tournament, as well as tracking player data using game's api.


## How to setup the Discord Bot
To setup the discord bot you will need a couple of things.
Before you begin, you will need a file named .env (just like that nothing else) in the same folder as the bot.py file

Within the .env file you will need to put the following operational keys:
(Note that the Google Sheets ID must be in double quotes, all other keys should be pasted as-is)

- BOT_TOKEN=
- GUILD_ID=
- CHANNEL_ID=
- GOOGLE_SHEETS_ID=
- GEMINI_API_KEY=
- RIOT_API_KEY=

Below the operational keys there are also some configuration items used for calculating a player's tier:
(These are the defaults as of the documentation period and subject to change as needed)
- unranked = 11
- iron = 10
- bronze = 9
- silver = 8 
- gold = 7 
- platinum = 6 
- emerald = 5 
- diamond = 4 
- master = 3 
- grandmaster = 2 
- challenger = 1 

- winratio = .67
- gamesplayed = 10


### How to make the discord BOT_TOKEN
You need to go to https://discord.com/developers/applications and create a new developer application.

You will be asked to name it and agree to the ToS

On the side bar, there is an option called bot, click that and it will allow you to build the bot for the application.

To get the bot token, you must click reset token.

This will display a token and you will copy paste that token into the .env file

It should look like BOT_TOKEN = ‘insert bot token here’

### How to get the GUILD_ID token 
This one is a lot simpler, you need to go to your discord client, enable discord developer mode, right click the server you want to use the bot in, then click copy server id

In case of the KSU League of Legends Discord Server, the ID is 752309075798392852

So it should look like GUILD_TOKEN = 752309075798392852

### How to get the CHANNEL_ID token 
Similar to obtaining the GUILD_ID token, right click on the channel in Discord and select copy channel id.

### How to get GOOGLE_SHEETS_ID
The sheet id is just the ID of the google sheet that you are trying to use. To find it, all you need to do is look at the url of your google sheet. You can find the id here in the URL:

docs.google.com/spreadsheets/d/ID_IS_HERE/

>[!Note]
This token must be in double quotes in the .env file

### How to setup Google API access 
Follow the Google tutorial to enable the Sheets API:

[https://developers.google.com/sheets/api/quickstart/python]

Once you have enabled and setup your api access in a project you must create a user for access:

Start by choosing the Go to OAuth consent screen button in the tutorial:
- Select External and click Create
- Fill in the 3 required fields, App Name, User email, and Developer contact and click Save and Continue
- On the Scopes screen, choose Add or Remove Scopes
- The easiest way to find the scope is type "sheets" in the filter
- Choose the auth/spreadsheets scope (the description says See, edit, create, and delete all your Google Sheets spreadsheets)
- Click Update and then Save and Continue
- Test users are not required so click Save and Continue again
- Now that the OAuth consent is completed, navigate to the Credentials page
- At the top, choose + Create Credentials and then Service Account
- Create a service account name, this will auto populate the ID field as well
- Click Create and Continue
- Choose Role->Basic->Owner and then click Continue
- Step 3 can be left empty, click Done to return to the Service Accounts screen
- Choose the newly created service account and then choose Keys at the top
- Select Add Key and Create new key with the key type being JSON and click Create
- Once created, a JSON file should have downloaded to your machine
- Rename this json file to "token.json" and place it in the root directory with bot.py
- Now copy the service account's full address (should end with .iam.gserviceaccount.com)
- Go to the Google Sheet you want to access and add that user as an editor
- Google sheets is now configured

### How to setup Google Gemini access
- Go to [https://ai.google.dev/] and click Get API key in Google AI Studio
- Click Create API key
- Select the project that was created above for Sheets and click Create API key in existing project
- A popup will show the key, click Copy and then paste this key into the .env file

### How to setup Riot API access
- Go to [https://developer.riotgames.com/] and click Sign Up Now
- Create an account or login to an existing account
- You should now be logged in on the dashboard page, click the red Register Product button
- Under PERSONAL API KEY, click Register Product
- Read and agree to the Policies
- Fill out the form and click Submit

### Installation of Packages
The Required Packages for this bot to be ran on a computer are the following:

- asyncio
- discord
- itertools
- dotenv
- python-gemini-api
- google-api-python-client 
- google-auth-httplib2 
- google-auth-oauthlib

To install the packages, run pip install <packagename> and it should install the package. Do this for all the packages and you should be good to move on
(Use pip3 for Mac/Linux)

### Database
The SQLITE database schema is built into the Python checkdatabase() method and is called every time the bot is started.  Most objects are only created if the database file does not already exist, but some objects are dropped and recreated each run to add custom configurations into the database.

Objects that are created only for a new database:
```
CREATE TABLE Player (
    discordID bigint PRIMARY KEY     	-- Unique Discord identifier for the player, will serve as PK
    , discordName nvarchar(64)			-- Player's Discord name
    , riotID nvarchar(64)				-- Player's Riot account name (Name#Tagline format)
    , lolRank varchar(32)				-- Player's LOL rank
    , preferences char(5)				-- Player's encoded lane preferences (1H-5L) in order of Top, Jungle, Mid, ADC, and Support
    , toxicity int                      -- Player's toxicity score
    , tieroverride int                  -- Used by admins to override player's tier score, 0 uses calculated value
    )

CREATE TABLE Games (
    gameID INTEGER PRIMARY KEY AUTOINCREMENT	    -- Unique ID to identify the game
    , gameDate date						-- Date of the game
    , gameNumber tinyint				-- Game number (1, 2, 3)	
    , gameLobby tinyint					-- Game Lobby (1, 2, 3) per 10 players
    , gameWinner varchar(4)				-- Team that won this game (Blue/Red)
    , isComplete bit                    -- Used to track incomplete games
    )

CREATE TABLE GameDetail (
    gameID int NOT NULL			-- Game ID joining back to the Games table
    , discordID bigint NOT NULL	-- Player ID joining back to the Player table
    , teamName varchar(32)		-- Team of the Player in this game ('Red', 'Blue', 'Participation')
    , gamePosition char(3)		-- Position played in this game (Top, Jng, Mid, ADC, Sup)
    , MVP bit					-- 0 = no MVP, 1 = MVP
    , FOREIGN KEY (gameID) REFERENCES Games (gameID)
    , FOREIGN KEY (discordID) REFERENCES Player (discordID)
    )

CREATE TABLE RankHistory (
    discordID bigint        -- Player ID joining back to the Player table 
    , changedate date       -- Date the player's rank changed
    , oldrank varchar(64)   -- Player's old rank
    , newrank varchar(64)   -- Player's new rank
    )
```

>[!Note]
The player table also has a trigger that populates the RankHistory table anytime the Rank column changes for a player.

There are also two Views only created on the first run:
vw_Player - this view calculates the Player's tier score, explained in more depth below
vw_Points - this view joins the Games and GameDetails table for an easy look at every player's score

This table is automatically dropped and recreated every time the bot is started.  This is because the Rank to Tier mappings from the .env file are loaded into this table which makes it configurable.  The table is very simple and contains the rank and the tier score assigned.

TierMapping (lolRank varchar(64), tier int)


In addition to the Rank to Tier mapping, there are two more configurations in the .env file, winratio and gamesplayed.
The values in these two variables is used to increase a player's calculated tier if they are performing well in the KSU league.
The database view vw_TierModifier is dropped and created on each run of the bot to add these two values, which is tied to the vw_Player object to adjust the tier if the criteria is met.

The default values are a winratio of .67 and gamesplayed 10.  This means that if the player has a 67% or higher win rate AND they have played 10+ games in the same rank, they will receive an extra 1 adjustment to their calculated tier.

>[!Tip]
The RankHistory comes into play in that last statement, that table is also used to determine the length of time in a rank and whether the win rate and games played occurred within the current rank.

## Starting the bot
Run the bot.py via python bot.py
(Use python3 for Mac/Linux)

## Matchmaking Guide
The matchmake command simply takes one parameter, the match number for the current day.

There are a few conditions that will stop the command, details are provided in the messages to try again.
- Any previous games that have not been completed with the /win command
- If the match number provided was already used today
- There is not a multiple of 10 users in the Player role

There are 3 global settings that affect matchmaking which can be changed anytime via the /settings command.
- MAX_DEGREE_TIER - this is the maximum difference allowed between players in opposing lanes, default is 2
- USE_RANDOM_SORT - this setting will only make a difference if there are more than 10 players, it will shuffle the list instead of sorting by tier to provide diversity and is True by default
- USE_AI_MATCHMAKE - this setting will change the matchmaking code to use a Google Gemini prompt instead of the Python algorithm and is False by default

>[!TIP]
Depending on the settings above and the tier configurations there is a chance you will get a message that no team could be formed.  If there are only 10 players this message means some adjustment will need to be made to either player(s) tiers or the allowable difference setting.  If there are 20 or more players AND the USE_RANDOM_SORT is set to True, the command can be retried a few times to keep shuffling the player list or random sort can be turned off.

### General functionality overview
Matchmaking is dependent on two items: a player's tier and a player's preferences.

- A player's tier is automatically calculated in a view in the database.
- The calculation relies on the .env mapping of League Rank to a tier as well as a winrate calculation
 - League Rank mappings can only be configured in the .env before starting the script
 - The calculation for increasing a player's tier can also only be changed prior to startup
 - The changes can be made to the .env and the bot restarted without causing issues
- Each player also has a tier override that the admin can use to set a static tier score

When matchmake is called, assuming all conditions are correct, the first thing that happens is the list of Discord IDs in the Player roles are sent to the database to create a list of the players' information.

### Python's algorithm
If USE_AI_MATCHMAKE is set to False the Python algorithm will be used to form two teams for each set of 10 players.

1. The balance_teams() method is called and the player list from the database is passed in
2. find_balanced_teams() is first called by passing a degree of 0, this would mean every opposing player is the same tier score (unlikely)
3. Every possible combination of the teams is created with itertools and looped through
4. The assign_roles method is called and players are sorted into lanes based on their preferences
5. The teams are then created and passed to the validate_team_matchup along with this run's allowed degree tier difference
6. If the validation succeeds the team is formed and output via embed.
7. If the validation fails it will continue through every combination possible, then back to the find_balanced_teams() method to determine if it should try with the next degree of tier difference
8. If no team can be formed it will output a message and the admin will need to consider changes to settings or tiers to continue

>[!TIP]
The MAX_DEGREE_TIER is exactly how it sounds, a **maximum** allowed difference.  The algorithm will attempt to first form teams with a 0 difference, then 1, and on up to the number specified in that parameter.

### Gemini AI Matchmaking
The Gemini method takes the same player list and creates a prompt by translating the list into a JSON string.  The output back from Gemini is specified in JSON as well and is parsed back out to create the Team classes.

### How Tier Calculations Work
As noted in the "How to setup the Discord Bot" and the "Database" section above, the League of Legend ranks are mapped to a tier score in the .env file.

Here is a look at the code in the view that calculates whether a player's win rate and games played qualify them for a tier adjustment.

```
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

    SELECT discordID, CASE WHEN GamesPlayed >= 10 AND WinRatio >= .67 THEN 1 ELSE 0 END tiermodifier
    FROM winratio
```
>[!Note]
The final select contains a CASE statement for WHEN "GamesPlayed >= 10 AND WinRatio >= .67", the 10 and .67 numbers are pulled from the .env and built into this view every time the bot is started to allow for custom settings.


This is a look at the Player view, here you see the Player table is joined to the TierMapping and vw_TierModifier objects for the most accurate, and customizable, tier calculation possible.
```
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
LEFT OUTER JOIN vw_TierModifier mod ON mod.discordID = Player.discordID
```
>[!Tip]
If a number exists in the "tieroverride" column for a player it will automatically override all calculations, including the win modifier.

## MVP Voting
MVP Voting launches directly after an admin sets the winner of a lobby.  Depending on the settings, the voting embed will either be sent via DM to elibile voters, or it will be sent to the channel.  Either method keeps all voting confidential, a player's vote is never stored with their identification.

Eligible voters are the 10 players in the specified game's lobby plus any volunteers.  

>[!Tip]
Volunteers can vote in every lobby, so if there were 3 lobbies at the same time, they can vote in all 3.

Voting lasts for 5 minutes, once the time expires the voting buttons are disabled and the winner is announced in the main channel.  If no player met the minimum number of votes setting, it will be announced that no one won the vote.  

>[!Tip]
Multiple players are allowed to win if there is a tie, but they still must meet the minimum number of votes so this should be rare.

Finally, when MVP voting starts, a new table is dynamically generated in the database using the game's ID.  This allows voting to run in parallel for multiple lobbies as well as allowing matchmaking to continue during the voting period.  Once voting ends the table is automatically dropped.

### DM Voting
- This will check if players have DM disabled so that it does not break, but those players will not have a chance to vote.
- The voting embed will be sent as a DM to eligible voters displaying 5 buttons, one for each player on the winning team.
- The buttons will disable after a 5 minute voting period.
- In DM mode, the buttons will also disable as soon as the player votes to prevent extra votes.  Sorry, no take backs.

### Channel voting
- With this method, disabling buttons applies to everyone, so additional checks take place.
- When anyone clicks a vote button in the channel it will first check their Discord ID is in the eligible voting group.
- If that passes it will then check to see if the player has voted on this game before.
  - An extra table was added to the database called "Voted" that stored the Discord ID and GameID.  This table is purged every time the bot starts.
- If a player does not pass the checks, they are informed of why they cannot vote.
- As with DM voting, after the 5 minutes pass the buttons are disabled.

## Admin Commands
Admin commands used for configurations, running games, and making changes.  Each command is listed below along with their parameters.  Optional parameters with a default are in bold.

### Matchmaking and Gameplay
- /checkin – This launches the check in embed for users to sign up for a game.
  - **timeout** - Time in seconds the check in embed is valid, this has a default of 900 seconds for 15 minutes.
- /players - This displays all users in a Player or Volunteer role and indicates if lobbies are ready.
- /volunteer - This launches the volunteer embed, this is used if there is not a number of players divisible by 10 so extra players can still participate.
- /matchmake - This will start the matchmaking process and create a lobby for every 10 players.  
  - match_number - This is the game/match number for the day, typically 1, 2, and 3.
- /remove - Clears all users from the Player and Volunteer role.
- /win - This will set the winning team for an active lobby and also launch the MVP voting period.
  - lobby - The lobby number of the game to set the winner for, must be a valid number.
  - winner - The name of the winning team, must be either blue or red.  Case does not matter.
- /activegames - This will display all active and open games and their lobby number.  

### View and Modify Player Data
- /toxicity - Adds 1 point of toxicity to the specified player.
  - username - This can be either the Discord display name or the Riot ID of the player, case does not matter.
- /setplayertier - This will set a player's tier to a static number instead of having their tier calculated by rank/wins.  
  - username - This can be either the Discord display name or the Riot ID of the player, case does not matter.
  - tier - The exact tier you want the player to be.  *Setting this to 0 will remove the override and their calculated tier is used again.*
- /showuser - Displays the information about a user from the database.
  - username - This can be either the Discord display name or the Riot ID of the player, case does not matter.

### Managing Settings and Exports
- /export - This launches an embed with buttons to allow you to export data from the database to Google Sheets.
- /cleargamedata - This will first create a backup of the bot.db file by appending BACKUP_ to the front and the current timestamp to the end, then delete all data from GameDetail and Games to reset the season.
  - reassurance - This parameter requires you to type, in all caps, **I KNOW WHAT I AM DOING** in order to allow the delete to continue.
- **/settings** - This command allows you to alter how aspects of the bot function.  Every parameter is optional so it will change only the settings you enter a value for.
  - use_ai - This controls whether the matchmaking uses Gemini AI or Python's algorithm.  Default setting is *False*.
  - random_sort - This controls whether the player list is sorted by tier or randomized to prevent duplicate groups and affects both matchmaking options.  Default setting is *True*.
  - max_tier - This is the highest difference between two opposing players that will be allowed in the matchmaking algorithm.  Default setting is *2*.
  - min_votes - The minimum number of votes a player must have to win the MVP vote.  Default setting is *3*.
  - vote_dm - Controls whether the MVP voting embed is sent to eligible players via DM or posted directly in the chat.  Default setting is *False*, which puts the vote in the channel.

[!Note]
The /cleargamedata uses a check (interaction.user.id != interaction.guild.owner.id) that the user is the guild owner, if this becomes an issue at any point with Discord's rules this check can be switched to use the admin check function instead, similar to how other admin commands are handled.

## Player Commands
Listing of player commands and their usage
- /riotid - This command is used by the player to set their Riot ID.
  - id - This is the user's Riot ID, in the required format of {NAME}{TAGLINE}.
- /fill - This command is used by the player to set their preferences all to 4, indicating a neutral stance on every position available.
- /roleselect - This launches an embed for the player with drop down selectors they can use to set individual lane preferences.  1 = most preferred and 5 = absolutely not.

## Using the bot - A Typical Scenario for the Admin
1. Ensure all /settings are how you want them for the first round. (You can always change it next round!)
2. Once enough users have come online, initiate the /checkin period.  *You may want to run /remove in case anyone is still in a role from a previous session.*
3. As the time gets close for the check in period to end, use the /players command to get an idea of the number of players.
4. If there are not a number of players divisible by 10, start the /volunteer command and keep checking with /players until you have an appropriate number.
5. Once you have an appropriate number of players, run /matchmake to generate the teams.
6. Play the game.
7. Use /win to set the winning team of each lobby, this also kicks off the MVP voting.  *If you can't remember which games are still open, use /activegames.*
8. If you have more games to play, it's best to use /remove to start fresh, then go back to step 1!

## Known issues
1.  The Gemini AI prompt generated very poor teams, it seemed to never be able to fully conform to either the player's preferences or the allowable difference between opposing lanes.  Better prompt engineering may improve this, or as Gemini improves this may perform better in the future, but as of this release it is not recommended.
2.  Not every command uses a "defer" in the messaging, this has never been an issue in testing, but if an error message like "This did not respond" occurs, it could mean that command took longer than 3 seconds and did not use a defer.  The issue with adding a defer to everything was the ephemeral setting could not be set per message when using it.