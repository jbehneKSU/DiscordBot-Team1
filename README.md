
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

## Running the bot
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

>[!CAUTION]
In its current form, the prompt has been unreliable in both following preferences AND adhering to the allowabled difference between opposing lane tiers.  Better prompt engineering may be necessary to improve results.


