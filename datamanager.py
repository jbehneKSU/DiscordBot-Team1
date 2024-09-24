from tkinter import *
from tkinter import ttk
import sqlite3

try:
    dbconn = sqlite3.connect("bot.db")
    dbconn.row_factory = sqlite3.Row
    cur = dbconn.cursor()

    cur.execute("""UPDATE Player SET discordID = REPLACE( REPLACE( discordID, CHAR(13), ''), CHAR(10), ''),
                discordName = REPLACE( REPLACE( discordName, CHAR(13), ''), CHAR(10), ''),
                riotID = REPLACE( REPLACE( riotID, CHAR(13), ''), CHAR(10), ''),
                lolRank = REPLACE( REPLACE( lolRank, CHAR(13), ''), CHAR(10), ''),
                preferences = REPLACE( REPLACE( preferences, CHAR(13), ''), CHAR(10), '')
                """)
    dbconn.commit()

except sqlite3.Error as e:
    print(e)       
    exit

#region FUNCTIONS
def focus_next_widget(event):
    event.widget.tk_focusNext().focus()
    return("break")

def saveplayer():
    cmd = "UPDATE Player SET discordName = ?, discordID = ?, riotID = ?, lolRank = ?, preferences = ?, toxicity = ? WHERE discordID = ?"
    args = (txtDiscordName.get(1.0, END), txtDiscordID.get(1.0, END), txtriotID.get(1.0, END), txtlolRank.get(1.0, END), 
            txtpreferences.get(1.0, END), txtToxicity.get(1.0, END), result[idx]["discordID"])
    dbconn.execute(cmd, args)
    dbconn.commit()
    loadPlayers()

def loadPlayers():
    cleartext()
    listbox.delete(0, END)
    cur.execute('''SELECT discordID, COALESCE(discordName, '') discordName, COALESCE(riotID, '') riotID, 
	COALESCE(lolRank, '') lolRank, COALESCE(preferences, '') preferences, COALESCE(toxicity, '') toxicity
	FROM Player
	ORDER BY discordName''')

    global result 
    result = cur.fetchall()
    for index, r in enumerate(result):
        listbox.insert(index, r['discordName'])

def addnew():
    cur.execute("INSERT INTO Player (discordName, discordID, riotID, lolRank, preferences, toxicity) VALUES ('<new player>', '-1', '', '', '', 0)")
    dbconn.commit()
    loadPlayers()

def delete():
    args = (result[idx]["discordID"],)
    cur.execute("DELETE FROM Player WHERE DiscordID = ?", args)
    dbconn.commit()
    loadPlayers()        

def onselect(evt):
    w = evt.widget

    if len(w.curselection()) == 0:
        return

    global idx
    idx = int(w.curselection()[0])

    txtDiscordName.delete(1.0, END)
    txtDiscordName.insert(END, result[idx]["discordName"])
    txtDiscordID.delete(1.0, END)
    txtDiscordID.insert(END, result[idx]["DiscordID"])
    txtriotID.delete(1.0, END)
    txtriotID.insert(END, result[idx]["riotID"])
    txtlolRank.delete(1.0, END)
    txtlolRank.insert(END, result[idx]["lolRank"])
    txtpreferences.delete(1.0, END)
    txtpreferences.insert(END, result[idx]["preferences"])            
    txtToxicity.delete(1.0, END)
    txtToxicity.insert(END, result[idx]["toxicity"])            

def cleartext():
    txtDiscordName.delete(1.0, END)
    txtDiscordID.delete(1.0, END)
    txtriotID.delete(1.0, END)
    txtlolRank.delete(1.0, END)
    txtpreferences.delete(1.0, END)
    txtToxicity.delete(1.0, END)


#Method to load the database with test player data
def create_data():
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

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
            (500003,'thegodapollo','Apollo','Silver','15552',0 );"""
        cur.execute(query)
        dbconn.commit()

    except sqlite3.Error as e:
        print (f'Database error occurred generating test date: {e}')

    finally:
        cur.close()
        dbconn.close() 

#endregion

#region APP_BASE
# create root window
root = Tk()
# root window title and dimension
root.title("KSU Discord Bot Data Manager")
# Set geometry (widthxheight)
root.geometry('500x350')

# Create tab view
tabControl = ttk.Notebook(root)
tabPlayerData = ttk.Frame(tabControl)
tabGameData = ttk.Frame(tabControl)
# tabConfiguration = ttk.Frame(tabControl)

tabControl.add(tabPlayerData, text='Player Data')
tabControl.add(tabGameData, text='Game Data')
# tabControl.add(tabConfiguration, text='Configuration')

tabControl.pack(expand=1, fill="both")
#endregion

# region PLAYER_TAB
# create listbox object
listbox = Listbox(tabPlayerData, height = 15, width = 20)

# Define text boxes and labels to edit data
lblDiscordName = Label(tabPlayerData, height=1, width=20, text="Discord ID")
lblDiscordID = Label(tabPlayerData, height=1, width=20, text="Discord Name")
lblriotID = Label(tabPlayerData, height=1, width=20, text="RIOT ID")
lbllolRank = Label(tabPlayerData, height=1, width=20, text="LOL Rank")
lblpreferences = Label(tabPlayerData, height=1, width=20, text="TJMAS Preferences")
lblToxicity = Label(tabPlayerData, height=1, width=20, text="Toxicity")

txtDiscordName = Text(tabPlayerData, height=1, width=20)
txtDiscordID = Text(tabPlayerData, height=1, width=20)
txtriotID = Text(tabPlayerData, height=1, width=20)
txtlolRank = Text(tabPlayerData, height=1, width=20)
txtpreferences = Text(tabPlayerData, height=1, width=20)
txtToxicity = Text(tabPlayerData, height=1, width=20)

# Define buttons
btnNew = Button(tabPlayerData, text="New", width=10, command=addnew)
btnSave = Button(tabPlayerData, text="Save", width=10, command=saveplayer)
btnDelete = Button(tabPlayerData, text="Delete", width=10, command=delete)

listbox.bind('<<ListboxSelect>>', onselect)

listbox.grid(row=1, column=0, rowspan=6, padx=10, pady=10)

lblDiscordName.grid(row=1, column=1)
lblDiscordID.grid(row=2, column=1)
lblriotID.grid(row=3, column=1)
lbllolRank.grid(row=4, column=1)
lblpreferences.grid(row=5, column=1)
lblToxicity.grid(row=6, column=1)

# txtDiscordID.config(state=DISABLED)
txtDiscordID.grid(row=1, column=2) 
txtDiscordName.grid(row=2, column=2)
txtriotID.grid(row=3, column=2) 
txtlolRank.grid(row=4, column=2) 
txtpreferences.grid(row=5, column=2) 
txtToxicity.grid(row=6, column=2) 

txtDiscordName.bind("<Tab>", focus_next_widget)
txtDiscordID.bind("<Tab>", focus_next_widget)
txtriotID.bind("<Tab>", focus_next_widget)
txtlolRank.bind("<Tab>", focus_next_widget)
txtpreferences.bind("<Tab>", focus_next_widget)

btnNew.grid(row=7, column=0, pady=10)
btnSave.grid(row=7, column=2)
btnDelete.grid(row=7, column=1)

#endregion PLAYER_TAB

# Load the player data into the player tab list
# create_data()
loadPlayers()

# Execute Tkinter
root.mainloop()      