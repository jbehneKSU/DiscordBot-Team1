from tkinter import *
from tkinter import ttk
import sqlite3

try:
    dbconn = sqlite3.connect("bot.db")
    dbconn.row_factory = sqlite3.Row
    cur = dbconn.cursor()

except sqlite3.Error as e:
    print(e)       
    exit

#region FUNCTIONS
def focus_next_widget(event):
    event.widget.tk_focusNext().focus()
    return("break")

def saveplayer():
    cmd = "UPDATE Player SET discordName = ?, discordID = ?, riotID = ?, lolRank = ?, preferences = ?, toxicity = ?, tieroverride = ? WHERE discordID = ?"
    args = (txtDiscordName.get(1.0, END), txtDiscordID.get(1.0, END), txtriotID.get(1.0, END), txtlolRank.get(1.0, END), 
            txtpreferences.get(1.0, END), txtToxicity.get(1.0, END), txtTierOverride.get(1.0, END), result[idx]["discordID"])
    dbconn.execute(cmd, args)
    dbconn.commit()
    loadPlayers()

def loadPlayers():
    clearplayertext()
    listbox.delete(0, END)
    cur.execute('''SELECT discordID, COALESCE(discordName, '') discordName, COALESCE(riotID, '') riotID, 
	COALESCE(lolRank, '') lolRank, COALESCE(preferences, '') preferences, COALESCE(toxicity, '') toxicity,
    COALESCE(tieroverride, '') tieroverride
	FROM Player
	ORDER BY discordName''')

    global result 
    result = cur.fetchall()
    for index, r in enumerate(result):
        listbox.insert(index, r['discordName'])

def addnewplayer():
    cur.execute("INSERT INTO Player (discordName, discordID, riotID, lolRank, preferences, toxicity, tieroverride) VALUES ('<new player>', '-1', '', '', '', 0, 0)")
    dbconn.commit()
    loadPlayers()

def deleteplayer():
    args = (result[idx]["discordID"],)
    cur.execute("DELETE FROM Player WHERE DiscordID = ?", args)
    dbconn.commit()
    loadPlayers()        

def onplayerselect(evt):
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
    txtTierOverride.delete(1.0, END)
    txtTierOverride.insert(END, result[idx]["tieroverride"])        

def clearplayertext():
    txtDiscordName.delete(1.0, END)
    txtDiscordID.delete(1.0, END)
    txtriotID.delete(1.0, END)
    txtlolRank.delete(1.0, END)
    txtpreferences.delete(1.0, END)
    txtToxicity.delete(1.0, END)
    txtTierOverride.delete(1.0, END)


#endregion FUNCTIONS

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
lblTierOverride = Label(tabPlayerData, height=1, width=20, text="Tier Override")

txtDiscordName = Text(tabPlayerData, height=1, width=20)
txtDiscordID = Text(tabPlayerData, height=1, width=20)
txtriotID = Text(tabPlayerData, height=1, width=20)
txtlolRank = Text(tabPlayerData, height=1, width=20)
txtpreferences = Text(tabPlayerData, height=1, width=20)
txtToxicity = Text(tabPlayerData, height=1, width=20)
txtTierOverride = Text(tabPlayerData, height=1, width=20)

# Define buttons
btnNew = Button(tabPlayerData, text="New", width=10, command=addnewplayer)
btnSave = Button(tabPlayerData, text="Save", width=10, command=saveplayer)
btnDelete = Button(tabPlayerData, text="Delete", width=10, command=deleteplayer)

listbox.bind('<<ListboxSelect>>', onplayerselect)

listbox.grid(row=1, column=0, rowspan=7, padx=10, pady=10)

lblDiscordName.grid(row=1, column=1)
lblDiscordID.grid(row=2, column=1)
lblriotID.grid(row=3, column=1)
lbllolRank.grid(row=4, column=1)
lblpreferences.grid(row=5, column=1)
lblToxicity.grid(row=6, column=1)
lblTierOverride.grid(row=7, column=1)

# txtDiscordID.config(state=DISABLED)
txtDiscordID.grid(row=1, column=2) 
txtDiscordName.grid(row=2, column=2)
txtriotID.grid(row=3, column=2) 
txtlolRank.grid(row=4, column=2) 
txtpreferences.grid(row=5, column=2) 
txtToxicity.grid(row=6, column=2) 
txtTierOverride.grid(row=7, column=2)

txtDiscordName.bind("<Tab>", focus_next_widget)
txtDiscordID.bind("<Tab>", focus_next_widget)
txtriotID.bind("<Tab>", focus_next_widget)
txtlolRank.bind("<Tab>", focus_next_widget)
txtpreferences.bind("<Tab>", focus_next_widget)

btnNew.grid(row=8, column=0, pady=10)
btnSave.grid(row=8, column=2)
btnDelete.grid(row=8, column=1)

#endregion PLAYER_TAB

#region GAME_TAB

#endregion GAME_TAB


# Load the player data into the player tab list
# create_data()
loadPlayers()

# Execute Tkinter
root.mainloop()      