from collections import defaultdict
import random
from operator import itemgetter
import sqlite3

dbconn = sqlite3.connect("bot.db")
cur = dbconn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS Player (
    discordID bigint PRIMARY KEY     	-- Unique Discord identifier for the player, will serve as PK
    , discordName nvarchar(64)			-- Player's Discord name
    , riotID nvarchar(64)				-- Player's LOL name
    , lolRank varchar(32)				-- Player's LOL rank
    , preferences char(5)				-- Player's encoded lane preferences (1H-5L) in order of Top, Jungle, Mid, ADC, and Support
    , toxicity int                      -- Player's toxicity score
    );""")

query = "DELETE FROM Player"
cur.execute(query)
dbconn.commit()

query = """INSERT INTO Player (discordID, discordName, riotID, lolRank, preferences, toxicity) VALUES
(500012,'crispten','Crisp Ten','Diamond','42414',0 ),
(500028,'supersix5','Omval','Silver','55215',0 ),
(500001,'ace_of_spades448','aceofspades44','Platinum','45414',0 ),
(500008,'sneckomode','CHR0NlC','Silver','55512',0 ),
(500015,'genjose','genjose','Platinum','25515',0 ),
(500002,'aerof','Aerof','Emerald','44444',0 ),
(500018,'imsoclean','ImSoClean','Master','44444',0 ),
(500026,'KigMoMo#5044','MoMo','Master','44444',0 ),
(500027,'Nombe?','NomBe','Emerald','44444',0 ),
(500030,'qartho','QarthO','Master','44444',0 ),
(500042,'vanquish4707','Vanquish','Master','44444',0 ),
(500044,'yolopotat0','yolopotat00','Platinum','44444',0 ),
(500014,'foodequalschef','Food','Silver','51525',0 ),
(500022,'lakexl','LakeXL','Emerald','51552',0 ),
(500032,'rainyydayy','Lily','Emerald','51552',0 ),
(500035,'returtle','ReTurtle','Emerald','51552',1 ),
(500023,'LordZed','LordZed','Silver','21555',0 ),
(500041,'tortuehuppee','tortue','Platinum','21555',0 ),
(500040,'cambo023','teahee','Gold','55125',0 ),
(500029,'han_sooyoung','Pika','Emerald','51255',0 ),
(500043,'xtri.','xTri','Platinum','44154',0 ),
(500004,'bemo#5322','bemo','Silver','53152',0 ),
(500013,'fizz13','Fizz','Emerald','25155',0 ),
(500016,'gogetyama','Gogetyama','Emerald','25155',0 ),
(500024,'LotusMustDie','Lotus','Gold','25155',0 ),
(500025,'mattietkd','MattieTKD','Diamond','25155',0 ),
(500031,'quentinmon','quentinmon','Bronze','25155',0 ),
(500020,'kelcior501','Kelcior','Silver','44454',0 ),
(500037,'snorlax0143','Snorlax','Emerald','44454',0 ),
(500007,'drchanchan','Chandler','Emerald','44445',1 ),
(500011,'corneal','Corneal','Emerald','45444',0 ),
(500017,'thegozerian','thegozarian','Platinum','45444',0 ),
(500039,'kitkat_riceball','Strwbry Mooncake','Emerald','54444',0 ),
(500034,'reedlau','Reed','Silver','44451',0 ),
(500033,'readthistwice','Readthistwice','Master','55551',0 ),
(500005,'bunkat','BunKat','Diamond','44441',99999 ),
(500006,'lilbusa','BUSA','Gold','55251',0 ),
(500019,'infiniteaim','InfiniteAim','Master','55251',0 ),
(500009,'chug1','Chug','Emerald','25551',1 ),
(500036,'ShadowMak03','ShadowMak','Silver','25551',0 ),
(500000,'apileoforanges','a wittle gwiefer','Diamond','15255',0 ),
(500010,'connero','conner101','Diamond','15255',0 ),
(500021,'kneesocks77','Kneesocks','Emerald','15255',0 ),
(500038,'neel1','Spoof','Silver','15253',0 ),
(500003,'thegodapollo','Apollo','Silver','15552',0 )
"""
cur.execute(query)
dbconn.commit()

cur.execute("SELECT riotID, lolRank, preferences FROM Player ORDER BY RANDOM() LIMIT 10")
players = cur.fetchall()


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


# Mapping of preferences

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
    balance_attempts = 10
    while not check_balance(team_red, team_blue, players) and balance_attempts >= 0:
        random.shuffle(players)
        team_red, team_blue = balanced_teams(players)
        balance_attempts -= 1
    
    return team_red, team_blue

team_red, team_blue = create_teams(players)

# for p in team_red:
    # players.index(p)

print("Red Team:", team_red)
print("Blue Team:", team_blue)
