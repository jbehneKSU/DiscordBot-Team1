import discord
import random
import asyncio

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Constants for Simulation
TEAM_1_PLAYERS = ["Player1", "Player2", "Player3", "Player4", "Player5"]
TEAM_2_PLAYERS = ["Player6", "Player7", "Player8", "Player9", "Player10"]
ALL_PLAYERS = TEAM_1_PLAYERS + TEAM_2_PLAYERS

# Game Event Simulation
def simulate_game():
    results = {}

    # Simulate stats for each player
    for player in ALL_PLAYERS:
        kills = random.randint(0, 15)
        deaths = random.randint(0, 15)
        assists = random.randint(0, 20)
        cs = random.randint(50, 300)  # Creeps Score (minions)
        results[player] = {"Kills": kills, "Deaths": deaths, "Assists": assists, "CS": cs}

    # Randomly determine which team wins
    winner = random.choice([1, 2])
    return results, winner

# Message Handler
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower() == "!startgame":
        await message.channel.send("Starting a simulated League of Legends match...")

        # Simulate game
        results, winner = simulate_game()

        # Display results
        await asyncio.sleep(2)  # Delay for effect
        await message.channel.send("Game has ended! Here are the results:\n")

        # Show results for Team 1
        team1_stats = "\n".join([f"{player}: {stats['Kills']} Kills, {stats['Deaths']} Deaths, {stats['Assists']} Assists, {stats['CS']} CS"
                                 for player, stats in results.items() if player in TEAM_1_PLAYERS])
        team2_stats = "\n".join([f"{player}: {stats['Kills']} Kills, {stats['Deaths']} Deaths, {stats['Assists']} Assists, {stats['CS']} CS"
                                 for player, stats in results.items() if player in TEAM_2_PLAYERS])

        await message.channel.send(f"**Team 1 Stats:**\n{team1_stats}")
        await message.channel.send(f"**Team 2 Stats:**\n{team2_stats}")

        # Announce winner
        await message.channel.send(f"**Team {winner} Wins!**")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

# Run the bot
client.run('YOUR_DISCORD_BOT_TOKEN')
