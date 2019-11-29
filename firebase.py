#External imports
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

#Internal imports
import config
import twilioInterface as textI

cred = credentials.Certificate('TOAFirebase.json')
default_app = firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://the-orange-alliance.firebaseio.com/'
    })

def loadAdminNums():
    adminList = []
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    userDB = db.reference('Users')
    levelDB = userDB.order_by_key().get()
    for number in phoneDB:
        try:
            if phoneDB[number]['uid']:
                if levelDB[phoneDB[number]['uid']]['level'] == 6:
                    adminList.append("+" + number)
            else:
                continue
        except:
            continue
    print(adminList)
    config.adminList = adminList

def optInOut(splitParts, userNum):
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    number = userNum
    userNum = userNum[1:]
    if userNum not in phoneDB:
        refDB.child(userNum).set({'opted': True})
        print("Phone number added to DB")
        refDB = db.reference('Phones')
        phoneDB = refDB.order_by_key().get()
        textI.sendText(number, "Welcome to TOAText! Send 'help' to receive a list of commands and how to use them!")
        return False
    if "quit" in splitParts or "stop" in splitParts:
        refDB.child(userNum).update({'opted': False})
        textI.sendText(number, "You have now opted out of ALL TOAText messages. Send START to rejoin")
        print(str(userNum) + " has opted out")
        return True
    elif "start" in splitParts:
        refDB.child(userNum).update({'opted': True})
        textI.sendText(number, "You have now rejoined TOAText and can use all the features")
        return False
    if not phoneDB[userNum]['opted']:
        print("An opted out user (" + str(number) + ") has tried to make a request")
        return True
    else:
        return False

def myTOA(msg, number):
    ansList = []
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    userNum = number[1:]
    try:
        if phoneDB[userNum]['uid'] != "":
            UID = str(phoneDB[userNum]['uid'])
            userDB = db.reference('Users')
            userSortDB = userDB.order_by_key().get()
            firstName = str(userSortDB[UID]["fullName"]).split(" ")[0]
            firstMsg = ""
            try:
                firstMsg += firstName + ", according to myTOA, you're on team " + str(userSortDB[UID]["team"])
            except:
                firstMsg += firstName + ", according to myTOA, you're not on a team"
            try:
                levelDefinitions = ["General User", "Team/Event Admin", "Regional Admin", "FIRST", "Moderator",
                                    "Admin"]
                if int(userSortDB[UID]["level"]) != 1:
                    firstMsg += ". Also, you have an account level of " + str(userSortDB[UID]["level"]) + " (" + \
                                levelDefinitions[int(userSortDB[UID]["level"]) - 1] + ")"
            except:
                firstMsg += ""
            ansList.append(firstMsg)
        else:
            print("That user exists and has no user ID")
    except:
        return ["Your phone number has not been linked to a myTOA profile (EC4)"]
    try:
        eventNumDB = list(userSortDB[UID]["favTeams"].keys())
    except AttributeError:
        eventNumDB = []
    if len(eventNumDB) != 0:
        if len(eventNumDB) == 1:
            teamStr = "Your favorite team is "
        else:
            teamStr = "Your favorite teams are "
        for i in eventNumDB:
            teamStr += str(i) + ", "
        teamStr = teamStr[:-2]
        ansList.append(teamStr)
    else:
       ansList.append("You have not set any favorite teams in your myTOA profile!")
    return ansList
