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
    cmd = "UPDATE Player SET discordName = ?, discordID = ?, lolID = ?, lolRank = ?, preferences = ?, toxicity = ? WHERE discordID = ?"
    args = (txtDiscordName.get(1.0, END), txtDiscordID.get(1.0, END), txtlolID.get(1.0, END), txtlolRank.get(1.0, END), 
            txtpreferences.get(1.0, END), txtToxicity.get(1.0, END), result[idx]["discordID"])
    dbconn.execute(cmd, args)
    dbconn.commit()
    loadPlayers()

def loadPlayers():
    cleartext()
    listbox.delete(0, END)
    cur.execute('''SELECT discordID, COALESCE(discordName, '') discordName, COALESCE(lolID, '') lolID, 
	COALESCE(lolRank, '') lolRank, COALESCE(preferences, '') preferences, COALESCE(toxicity, '') toxicity
	FROM Player
	ORDER BY discordName''')

    global result 
    result = cur.fetchall()
    for index, r in enumerate(result):
        listbox.insert(index, r['discordName'])

def addnew():
    cur.execute("INSERT INTO Player (discordName, discordID, lolID, lolRank, preferences, toxicity) VALUES ('<new player>', '-1', '', '', '', 0)")
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
    txtlolID.delete(1.0, END)
    txtlolID.insert(END, result[idx]["lolID"])
    txtlolRank.delete(1.0, END)
    txtlolRank.insert(END, result[idx]["lolRank"])
    txtpreferences.delete(1.0, END)
    txtpreferences.insert(END, result[idx]["preferences"])            
    txtToxicity.delete(1.0, END)
    txtToxicity.insert(END, result[idx]["toxicity"])            

def cleartext():
    txtDiscordName.delete(1.0, END)
    txtDiscordID.delete(1.0, END)
    txtlolID.delete(1.0, END)
    txtlolRank.delete(1.0, END)
    txtpreferences.delete(1.0, END)
    txtToxicity.delete(1.0, END)


#Method to load the database with test player data
def create_data():
    try:
        dbconn = sqlite3.connect("bot.db")
        cur = dbconn.cursor()

        query = """INSERT INTO Player (discordID, discordName, lolID, lolRank, preferences, toxicity) VALUES
            (123456789012345678, 'Player1', 'LOLPlayer1', 'Diamond', '01234', 2),
            (123456789012345679, 'Player2', 'LOLPlayer2', 'Platinum', '10100', 1),
            (123456789012345680, 'Player3', 'LOLPlayer3', 'Gold', '00321', 3),
            (123456789012345681, 'Player4', 'LOLPlayer4', 'Silver', '22222', 4),
            (123456789012345682, 'Player5', 'LOLPlayer5', 'Bronze', '00001', 5),
            (123456789012345683, 'Player6', 'LOLPlayer6', 'Diamond', '43210', 2),
            (123456789012345684, 'Player7', 'LOLPlayer7', 'Platinum', '32100', 3),
            (123456789012345685, 'Player8', 'LOLPlayer8', 'Gold', '21000', 4),
            (123456789012345686, 'Player9', 'LOLPlayer9', 'Silver', '10001', 5),
            (123456789012345687, 'Player10', 'LOLPlayer10', 'Bronze', '00400', 1),
            (123456789012345688, 'Player11', 'LOLPlayer11', 'Diamond', '43210', 2),
            (123456789012345689, 'Player12', 'LOLPlayer12', 'Platinum', '32100', 3),
            (123456789012345690, 'Player13', 'LOLPlayer13', 'Gold', '21030', 4),
            (123456789012345691, 'Player14', 'LOLPlayer14', 'Silver', '11234', 5),
            (123456789012345692, 'Player15', 'LOLPlayer15', 'Bronze', '11111', 1),
            (123456789012345693, 'Player16', 'LOLPlayer16', 'Diamond', '43210', 2),
            (123456789012345694, 'Player17', 'LOLPlayer17', 'Platinum', '32100', 3),
            (123456789012345695, 'Player18', 'LOLPlayer18', 'Gold', '21000', 4),
            (123456789012345696, 'Player19', 'LOLPlayer19', 'Silver', '10010', 5),
            (123456789012345697, 'Player20', 'LOLPlayer20', 'Bronze', '03420', 1);"""
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
lbllolID = Label(tabPlayerData, height=1, width=20, text="LOL ID")
lbllolRank = Label(tabPlayerData, height=1, width=20, text="LOL Rank")
lblpreferences = Label(tabPlayerData, height=1, width=20, text="TJMAS Preferences")
lblToxicity = Label(tabPlayerData, height=1, width=20, text="Toxicity")

txtDiscordName = Text(tabPlayerData, height=1, width=20)
txtDiscordID = Text(tabPlayerData, height=1, width=20)
txtlolID = Text(tabPlayerData, height=1, width=20)
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
lbllolID.grid(row=3, column=1)
lbllolRank.grid(row=4, column=1)
lblpreferences.grid(row=5, column=1)
lblToxicity.grid(row=6, column=1)

# txtDiscordID.config(state=DISABLED)
txtDiscordID.grid(row=1, column=2) 
txtDiscordName.grid(row=2, column=2)
txtlolID.grid(row=3, column=2) 
txtlolRank.grid(row=4, column=2) 
txtpreferences.grid(row=5, column=2) 
txtToxicity.grid(row=6, column=2) 

txtDiscordName.bind("<Tab>", focus_next_widget)
txtDiscordID.bind("<Tab>", focus_next_widget)
txtlolID.bind("<Tab>", focus_next_widget)
txtlolRank.bind("<Tab>", focus_next_widget)
txtpreferences.bind("<Tab>", focus_next_widget)

btnNew.grid(row=7, column=0, pady=10)
btnSave.grid(row=7, column=2)
btnDelete.grid(row=7, column=1)

#endregion PLAYER_TAB

# Load the player data into the player tab list
loadPlayers()

# Execute Tkinter
root.mainloop()      