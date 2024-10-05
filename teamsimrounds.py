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
        await message.channel.send("Starting a best of 3 series of simulated League of Legends matches...\n")
        
        team1_wins = 0
        team2_wins = 0

        # To accumulate stats across rounds
        cumulative_stats = {player: {"Kills": 0, "Deaths": 0, "Assists": 0, "CS": 0} for player in ALL_PLAYERS}

        for round_num in range(1, 4):  # Best of 3 (3 rounds)
            await message.channel.send(f"**Round {round_num} is starting...**")

            # Simulate the game for this round
            results, winner = simulate_game()

            # Update cumulative stats
            for player in ALL_PLAYERS:
                cumulative_stats[player]["Kills"] += results[player]["Kills"]
                cumulative_stats[player]["Deaths"] += results[player]["Deaths"]
                cumulative_stats[player]["Assists"] += results[player]["Assists"]
                cumulative_stats[player]["CS"] += results[player]["CS"]

            # Track wins per team
            if winner == 1:
                team1_wins += 1
            else:
                team2_wins += 1

            # Show results for this round
            team1_stats = "\n".join([f"{player}: {results[player]['Kills']} Kills, {results[player]['Deaths']} Deaths, {results[player]['Assists']} Assists, {results[player]['CS']} CS"
                                    for player in TEAM_1_PLAYERS])
            team2_stats = "\n".join([f"{player}: {results[player]['Kills']} Kills, {results[player]['Deaths']} Deaths, {results[player]['Assists']} Assists, {results[player]['CS']} CS"
                                    for player in TEAM_2_PLAYERS])

            await message.channel.send(f"**Round {round_num} Results:**\n")
            await message.channel.send(f"**Team 1 Stats:**\n{team1_stats}")
            await message.channel.send(f"**Team 2 Stats:**\n{team2_stats}")

            # Announce round winner
            await message.channel.send(f"**Team {winner} Wins Round {round_num}!**\n")
            await asyncio.sleep(2)  # Short delay between rounds

        # Announce final winner based on most rounds won
        if team1_wins > team2_wins:
            final_winner = 1
        else:
            final_winner = 2

        await message.channel.send(f"**After 3 Rounds, Team {final_winner} Wins the Best of 3 Series!**\n")

        # Display cumulative stats across all rounds
        await message.channel.send(f"**Cumulative Stats Across All 3 Rounds:**\n")

        team1_cumulative = "\n".join([f"{player}: {cumulative_stats[player]['Kills']} Kills, {cumulative_stats[player]['Deaths']} Deaths, {cumulative_stats[player]['Assists']} Assists, {cumulative_stats[player]['CS']} CS"
                                      for player in TEAM_1_PLAYERS])
        team2_cumulative = "\n".join([f"{player}: {cumulative_stats[player]['Kills']} Kills, {cumulative_stats[player]['Deaths']} Deaths, {cumulative_stats[player]['Assists']} Assists, {cumulative_stats[player]['CS']} CS"
                                      for player in TEAM_2_PLAYERS])

        await message.channel.send(f"**Team 1 Cumulative Stats:**\n{team1_cumulative}")
        await message.channel.send(f"**Team 2 Cumulative Stats:**\n{team2_cumulative}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

# Run the bot
client.run('YOUR_DISCORD_BOT_TOKEN')
