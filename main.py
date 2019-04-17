import requests
from twilio import twiml
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import random as rand
import threading
import json
import time
from flask import Flask, request, make_response
from fuzzywuzzy import fuzz
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

cred = credentials.Certificate('TOAFirebase.json')
default_app = firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://the-orange-alliance.firebaseio.com/'
})

app = Flask(__name__)
apiURL = "http://theorangealliance.org/api/"

apiHeaders = {'content-type': 'application/json',
              'X-TOA-KEY': '',
              'X-Application-Origin': 'TOAText'}

functionsURL = "https://functions.theorangealliance.org/"

functionsHeaders = {'Authorization': ''}

# r = requests.get(apiURL, headers=apiHeaders)

# defines whether the program is active or not
disableMode = 0

# numbers allowed to use admin cmds
adminList = []

#numbers allowed to use event admin cmds
eventAdminList = []

# numbers who get pinged upon use
pingList = []

# numbers who recieve help texts
helpNumList = []

# all Teams in first
allTeams = []

optOutNums = []

twilioAccountID = ""
twilioAuth = ""
webhookKey = ""

# global val for average comp last weekend
autoSum = 0
teleOpSum = 0

#list of numbers who want to use the 810 number
numTwoList = []

mainNum = ""
secNum = ""
class incomingText(threading.Thread):  # Thread created upon request
    def __init__(self, name, sendnum, msgbody):
        threading.Thread.__init__(self)
        self.name = name
        self.sendnum = sendnum
        self.msgbody = msgbody

    def run(self):
        print("Fetching request to " + self.sendnum)
        checkTeam(self.msgbody, self.sendnum)
        print("Finished request to " + self.sendnum)

@app.route("/sms", methods=['POST'])
def receiveText():  # Code executed upon receiving text
    global numTwoList
    twilioNum = request.form['To']
    number = request.form['From']
    message_body = request.form['Body']
    # print("Received from: " + str(number))
    if twilioNum == "+18102020701" and number not in numTwoList:
        numTwoList.append(number)
    elif twilioNum == "+16146666924" and number in numTwoList:
        numTwoList.remove(number)
    resp = MessagingResponse()
    t = incomingText(number, number, message_body)
    t.start()
    return (str(resp))

@app.route("/receiveHook", methods=['POST'])
def newLiveAlerts(): #Captures generic match info
    if webhookKey == request.headers.get('webhookKey') or request.environ['REMOTE_ADDR'] == "127.0.0.1":
        matchInfo = request.get_json(force=True)
        if matchInfo['message_type'] != "match_scored":
            return 'wrong_type'
        print(str(matchInfo))
        refDB = db.reference('liveEvents')
        eventsDB = refDB.order_by_key().get()
        redList = []
        blueList = []
        personR = requests.get(apiURL + "match/" + matchInfo['message_data']['match_key'] + "/participants",headers=apiHeaders)
        for i in range(len(personR.json())):
            if personR.json()[i]["station"] < 19:
                redList.append(personR.json()[i]["team_key"])
            elif personR.json()[i]["station"] > 19:
                blueList.append(personR.json()[i]["team_key"])
        try:
            userMsg = str(matchInfo['message_data']["match_name"]) + " just ended! "
            userMsg += str(matchInfo['message_data']["red_score"]) + " red " + str(redList) + ", "
            userMsg += str(matchInfo['message_data']["blue_score"]) + " blue " + str(blueList) + " "
        except:
            userMsg = str(matchInfo['message_data']["match_name"]) + " just ended! "
            userMsg += str(matchInfo['message_data']["red_score"]) + " red, "
            userMsg += str(matchInfo['message_data']["blue_score"]) + " blue"
        for usersNum in eventsDB[matchInfo['message_data']["event_key"]]:
            sendText("+" + usersNum, userMsg)
        if webhookKey == request.headers.get('webhookKey'):
            resBody = '{"_code":200,"_message":"Key request successful"}'
        elif request.environ['REMOTE_ADDR'] == "127.0.0.1":
            resBody = '{"_code":200,"_message":"Localhost request successful"}'
    else:
        resBody = '{"_code":401,"_message":"Missing or invalid key"}'
    res = make_response(str(resBody))
    res.headers['Content-Type'] = 'application/json'
    print(resBody + " - " + str(request.environ['REMOTE_ADDR']))
    return res

def sendText(number, msg, override = False):  # Code to send outgoing text
    global numTwoList
    account_sid = twilioAccountID
    auth_token = twilioAuth
    client = Client(account_sid, auth_token)
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    userNum = number[1:]
    if not phoneDB[userNum]['opted'] and not override:
        return
    if "+1" in number and number in numTwoList:
        message = client.messages \
            .create(
            body=str(msg),
            from_='+18102020701',
            to=str(number)
        )
    elif "+1" in number:
        message = client.messages \
            .create(
            body=str(msg),
            from_='+16146666924',
            to=str(number)
        )
    elif "+972" in number:
        message = client.messages \
            .create(
            body=str(msg),
            from_='+972525932576',
            to=str(number)
        )


command_descriptions = {
    "location": "responds with city and state a team is from",
    "name": "responds with team name and community/long name",
    "startyear": "responds with a team's rookie year",
    "website": "responds with a team's website",
    "events": "responds with all events a team has participated in during the current season",
    "awards": "responds with all awards a team has won (current season) and where",
    "about": "wanna know about TOAText? Use the About Command",
    "newcmds": "use this to know what features are new to TOAText",
    "flip": "flips a virtual coin pseudo-randomly",
    "searchtn": "attempts to search for a team number by team name. searchTN:Rust In Pieces or searchTN exactname Rust In Pieces",
    "matchinfo": "gives breakdowns on a team's matches. " +
                 "Use format [team#]:matchInfo:[matchKey] to return details about a match. " +
                 "Use format [team#]:matchInfo:minMax to return details about their best and worst matches. " +
                 "Use format [team#]:matchInfo:topThree to return details about their top three matches",
    "livestats": "Can be used if event is running on live Channel 1 (Check with checklives)" +
                 "Use format [team#]:livestats:ranking to return a teams current ranking " +
                 "Use format [team#]:livestats:topteams to return the top 3 teams at the tournament/event",
    "sendhelp": "pings admins in help list with your number and issue",
    "avgtotalscore": "responds with average auto and teleOp scores for previous weekend",
    "avgtotalpoints": "responds with average auto and teleOp scores for previous weekend",
    "addlive": "toggles whether a user is receiving live text notifications for the currently selected game",
    "checklives": "shows what events are currently using live scoring",
    "addlive2": "toggles whether a user is receiving live text notifications for the currently selected game, channel 2 is less in-depth",
    "avgscore": "responds with approx. average score for the alliances a team has been on",
    "avgpoints": "responds with approx. average score for the alliances a team has been on",
    "mytoa": "responds with a users team and favorite team, if they have a myTOA account",
    "opr": "responds with the OPR for a team at every event they've been to"
}
admin_command_descriptions = {
    "freeze": "locks/disables TOAText in case of error or maintenance",
    "metrics": "responds with all team metrics",
    "metrics2": "responds with all other recorded metrics",
    "pingme": "toggles if you get pinged when a user uses TOAText",
    "banhelp": "bans a number from using the sendhelp feature [banhelp:number (with +1)]",
    "joinhelp": "toggles if users can message you with issues",
    "sendhelp": "responds to a sendhelp user (sendhelp:number(with +1):msg",
    "updateavg": "updates average score to previous weekends"
}
event_command_descriptions = {
    "togglelive": "toggles the state of live scoring [togglelive:[matchKey]]",
    "liveskip": "Skips over live match if a single match is missing from DataSync",
    "livequalmode": "Prevents advancement from quals if toggled"
}


def respond_by_command(descriptions, splitParts, number):
    for command, description in descriptions.items():
        if command in splitParts:
            sendText(number, command + " - " + description)
            return True
    return False

def checkHelp(splitParts, number):  # Code to check if help was requested
    sent = False
    if "?" in splitParts or "helpme" in splitParts or "help" in splitParts:
        print("Help requested by " + str(number))
        if number in adminList:
            sent = respond_by_command(admin_command_descriptions, splitParts, number)
        if not sent and number in eventAdminList:
            sent = respond_by_command(event_command_descriptions, splitParts, number)
        if not sent:
            sent = respond_by_command(command_descriptions, splitParts, number)
        if not sent:
            sendText(number,
                     "Begin text with team number and then spaces or : to separate commands. Send a team number with nothing else to be provided a brief overview")
            sendText(number,
                     "Houston Worlds special commands - addJemison + addFranklin (to join live alerts!), streams, schedule")
            sendText(number,
                     "Available team requests are: location, name, startYear, website, events, awards, avgScore, matchinfo, livestats, OPR")
            sendText(number,
                     "Available non-team requests are: avgTotalScore, about, flip, searchTN. Example - 15692:location:name:events or 15692 shortname awards")
            adminHelpStr = ""
            if number in adminList:
                adminHelpStr += "Admin requests: checkStatus, freeze, metrics, metrics2, pingme, updateavg, updateAdmins, serverstatus"
            if number in eventAdminList:
                sendText(number, adminHelpStr)
            sendText(number,
                     "Use ?:[command] to know more! Text STOP to opt-out of using TOAText. Use START to opt back into TOAText.")
        return True
    elif "about" in splitParts:
        sendText(number,
                 "TOAText is a portable, on-the-go version of The Orange Alliance. It can provide information about teams, along with statistics")
        sendText(number, "Created by Team 15692 in collaboration with The Orange Alliance. Special thanks to Dominic Hupp for maintaining this project")
        sendText(number, "To know more about any commands, use ?:[command] or help:[command]")
        return True
    elif "newcmds" in splitParts:
        sendText(number, "New features - checklives, livestats, matchinfo, addLive, searchTN, OPR")
        return True
    elif "pickup" in splitParts:
        pickupList = ["Baby, are you FTC? Because everyone overlooks you and they shouldn't",
                     "Are you a tank drive? Cause I'd pick you every time",
                     "Are you a rivet, because without you I'd fall apart",
                     "Don't call me Java, because I'll never treat you like an object",
                     "Baby are you a swerve drive 'cause you spin me right round",
                     "Are you a compass?  Because you're a-cute and I love having you around",
                     "Hey baby, are you a soldering iron because I melt when I see you", "You're FIRST in my heart",
                     "Are you FTC? Because I'll care about you when nobody else will",
                     "Are you a robot, cause you just drove away with my heart",
                     "Not in elims? You're always the first seed in my heart!!",
                     "Are you hook and loop tape? Because I think I'm stuck on you",
                     "Are you the end game of Rover Ruckus, because I just wanna hang out",
                     "Are you a mineral? Cause picking you up is my goal"]
        randomNum = rand.randint(0, len(pickupList) - 1)
        sendText(number, pickupList[randomNum])
        print("User used pickup command")
        return True
    else:
        return False
    '''elif "checklives" in splitParts:
        runningKeys = ""
        if liveMatchKey == "":
            runningKeys += "addLive - none; "
        else:
            runningKeys += "addLive - " + str(liveMatchKey) + "; "
        if liveMatchKeyTwo == "":
            runningKeys += "addLive2 - none; "
        else:
            runningKeys += "addLive2 - " + str(liveMatchKeyTwo) + "; "
        if liveMatchKeyThree == "":
            runningKeys += "addLive3 - none; "
        else:
            runningKeys += "addLive3 - " + str(liveMatchKeyThree) + "; "
        if liveMatchKeyFour == "":
            runningKeys += "addLive4 - none; "
        else:
            runningKeys += "addLive4 - " + str(liveMatchKeyFour) + "; "
        if liveMatchKeyFive == "":
            runningKeys += "addLive5 - none; "
        else:
            runningKeys += "addLive5 - " + str(liveMatchKeyFive) + "; "
        sendText(number, str(runningKeys))
        return True'''

def champsCmds(number, splitParts):
    if "streams" in splitParts or "stream" in splitParts:
        textStr = "Streams: \n"
        textStr += "Franklin - https://player.twitch.tv/?channel=firstinspires_franklin \n"
        textStr += "Jemison - https://player.twitch.tv/?channel=firstinspires_jemison"
        sendText(number, textStr)
        sendText(number, "First Championship Channel - https://player.twitch.tv/?channel=firstinspires")
        return True
    elif "schedule" in splitParts:
        textStr = "Schedule: \n"
        textStr += "Franklin - http://toa.events/1819-CMP-HOU1 \n"
        textStr += "Jemison - http://toa.events/1819-CMP-HOU2"
        sendText(number, textStr)
        return True
    return False

def avgPoints(number, splitParts):  # Average total points
    if "avgtotalscore" in splitParts or "avgtotalpoints" in splitParts:
        print(number + " requested average score")
        sendText(number, "Average auto score - " + str(round(autoSum, 2)) + " || Average TeleOp score - " + str(
            round(teleOpSum, 2)) + " || Average score - " + str(round(float(autoSum + teleOpSum), 2)))
        return True

def addLive(number, splitParts):  # Adds users to live alert threads Franklin or Jemison
    '''if "addlive" in splitParts and liveMatchKey != "":
        print(str(number) + " Used AddLive")
        refDB = db.reference('liveEvents/' + str(liveMatchKey).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if number[1:] in eventDB:
            refDB.update({str(number[1:]): None})
            sendText(number, "You have been removed from the live scoring alerts")
        elif number[1:] not in eventDB:
            try:
                refDB.update({str(number[1:]): True})
            except AttributeError:
                refDB.set({str(number[1:]): True})
            sendText(number, "You have been added to the live scoring alerts. Send addLive again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive" in splitParts:
        sendText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addlive2" in splitParts and liveMatchKeyTwo != "":
        print(str(number) + " Used AddLive2")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyTwo).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if number[1:] in eventDB:
            refDB.update({str(number[1:]): None})
            sendText(number, "You have been removed from the live scoring alerts")
        elif number[1:] not in eventDB:
            try:
                refDB.update({str(number[1:]): True})
            except AttributeError:
                refDB.set({str(number[1:]): True})
            sendText(number, "You have been added to the live scoring alerts. Send addLive2 again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive2" in splitParts:
        sendText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addliveftcscores" in splitParts:
        print(str(number) + " Used addliveftcscores")
        if number in FTCScoresList:
            FTCScoresList.remove(number)
            sendText(number, "You have been removed from the live scoring alerts")
        elif number not in FTCScoresList:
            FTCScoresList.append(number)
            sendText(number, "You have been added to the live scoring alerts. Send addliveftcscores again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    if "addlive3" in splitParts and liveMatchKeyThree != "":
        print(str(number) + " Used AddLive3")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyThree).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if number[1:] in eventDB:
            refDB.update({str(number[1:]): None})
            sendText(number, "You have been removed from the live scoring alerts")
        elif number[1:] not in eventDB:
            try:
                refDB.update({str(number[1:]): True})
            except AttributeError:
                refDB.set({str(number[1:]): True})
            sendText(number, "You have been added to the live scoring alerts. Send addLive3 again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive3" in splitParts:
        sendText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addlive4" in splitParts and liveMatchKeyFour != "":
        print(str(number) + " Used AddLive4")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyFour).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if number[1:] in eventDB:
            refDB.update({str(number[1:]): None})
            sendText(number, "You have been removed from the live scoring alerts")
        elif number[1:] not in eventDB:
            try:
                refDB.update({str(number[1:]): True})
            except AttributeError:
                refDB.set({str(number[1:]): True})
            sendText(number, "You have been added to the live scoring alerts. Send addLive4 again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive4" in splitParts:
        sendText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addlive5" in splitParts and liveMatchKeyFive != "":
        print(str(number) + " Used AddLive4")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyFive).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if number[1:] in eventDB:
            refDB.update({str(number[1:]): None})
            sendText(number, "You have been removed from the live scoring alerts")
        elif number[1:] not in eventDB:
            try:
                refDB.update({str(number[1:]): True})
            except AttributeError:
                refDB.set({str(number[1:]): True})
            sendText(number, "You have been added to the live scoring alerts. Send addLive5 again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive5" in splitParts:
        sendText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True'''
    if "add" in splitParts and "franklin" in splitParts or "addfranklin" in splitParts:
        franklinKey = "1819-CMP-HOU1"
        refDB = db.reference('liveEvents/' + str(franklinKey).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if number[1:] in eventDB:
            refDB.update({str(number[1:]): None})
            sendText(number, "You have been removed from the live scoring alerts")
        elif number[1:] not in eventDB:
            try:
                refDB.update({str(number[1:]): True})
            except AttributeError:
                refDB.set({str(number[1:]): True})
            sendText(number, "You have been added to the live scoring alerts for Houston Worlds - Franklin Division. Send 'Add Franklin' again to be removed")
            sendText(number, "The Orange Alliance is NOT responsible for any missed matches. Please be responsible and best of luck!")
        return True
    if "add" in splitParts and "jemison" in splitParts or "addjemison" in splitParts:
        jemisonKey = "1819-CMP-HOU2"
        refDB = db.reference('liveEvents/' + str(jemisonKey).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if number[1:] in eventDB:
            refDB.update({str(number[1:]): None})
            sendText(number, "You have been removed from the live scoring alerts")
        elif number[1:] not in eventDB:
            try:
                refDB.update({str(number[1:]): True})
            except AttributeError:
                refDB.set({str(number[1:]): True})
            sendText(number, "You have been added to the live scoring alerts for Houston Worlds - Jemison Division. Send 'Add Jemison' again to be removed")
            sendText(number, "The Orange Alliance is NOT responsible for any missed matches. Please be responsible and best of luck!")
        return True

def returnErrorMsg(error, number):  # Error messages
    errorMsgText = "Hey there! Thats not very nice of you! (ECU)"
    errorList = ["Whoops. Someone must've forgotten to use a grounding strap!", "This is really grinding my gears",
             "I must be a swerve drive, because apparently I never work!", "Hey there! Thats not very nice of you!",
             "Just remember, goBILDA or go home", "... Bestrix.",
             "Hold your horses, that's not very GP of you",
             "Try again. The delivery robot strafed the wrong direction",
             "I'm still waiting... and waiting... and waiting"]
    randomNum = rand.randint(0, len(errorList)-1)
    errorMsgText = errorList[randomNum]
    if error == 'invalTeam':  # Missing Team Arguement
        errorMsgText += " (EC1)"
    if error == 'falseArg':  # Uses only unreal args
        errorMsgText += " (EC2)"
    if error == "PTError":
        errorMsgText += " (EC4)"
    if error != "valDay":
        errorMsgText += "  [For help, text 'help' or '?']"
    sendText(number, errorMsgText)

def parseRequest(number, userRequest):  # Turns user request into usable data
    # requestParts = userRequest.split(',')
    merge_expression_groups = [
        ("send", "help"),
        ("start", "year"),
        ("avg", "score"),
        ("avg", "points"),
        ("avg", "total", "points"),
        ("match", "info"),
        ("add", "live"),
        ("add", "live2"),
        ("add", "live3"),
        ("add", "live4"),
        ("add", "live5"),
        ("check", "lives"),
        ("check", "status"),
        ("ping", "me"),
        ("update", "avg"),
        ("update", "admins"),
        ("join", "help"),
        ("toggle", "live"),
        ("toggle", "live2"),
        ("toggle", "live3"),
        ("live", "stats"),
        ("live", "stats2"),
        ("live", "stats3"),
        ("min", "max"),
        ("top", "three"),
        ("short", "name"),
        ("get", "score"),
        ("mass", "msg")
    ]
    if ":" in userRequest:
        splitParts = userRequest.lower().replace(" ", "").split(":")
    else:
        splitParts = userRequest.lower().split(" ")
        for expr_group in merge_expression_groups:
            for i in range(0, len(splitParts) - len(expr_group) + 1):
                sublist = splitParts[i:i + len(expr_group)]
                if tuple(sublist) == expr_group:
                    for n in range(i + 1, i + len(expr_group)):
                        splitParts.pop(n)
                    splitParts[i] = ''.join(expr_group)
                    break
    # print(splitParts)
    return splitParts

def checkName(number, splitParts, raw):
    if "searchtn" in splitParts:
        if not splitParts[splitParts.index("searchtn") + 1].isdigit() and "exactname" in splitParts:
            if ":" in raw:
                searchingName = str(raw.split(":", 2)[2]).lower().replace(" ", "")
            else:
                searchingName = str(raw.split(" ", 2)[2]).lower().replace(" ", "")
            print(str(number) + " is looking for team name: " + str(searchingName))
            found = False
            possible = ""
            for i in range(len(allTeams)):
                try:
                    if allTeams[i]["team_name_short"].lower().replace(" ", "") == searchingName:
                        possible += str(allTeams[i]["team_key"]) + ", "
                        found = True
                except AttributeError:
                    continue
            if found == False:
                sendText(number, "That team name was not found. Please try again")
            elif found == True:
                if ":" in raw:
                    searchingName = str(raw.split(":", 2)[2])
                else:
                    searchingName = str(raw.split(" ", 2)[2])
                sendText(number, str(searchingName) + " could be team " + str(possible[:-2]))
        elif not splitParts[splitParts.index("searchtn") + 1].isdigit():
            if ":" in raw:
                searchingName = str(raw.split(":", 1)[1]).lower().replace(" ", "")
            else:
                searchingName = str(raw.split(" ", 1)[1]).lower().replace(" ", "")
            print(str(number) + " is looking for team name: " + str(searchingName))
            found = False
            possible = ""
            if searchingName != "robotics" and searchingName != "robots" and searchingName != "bots" and searchingName != "robotic":
                for i in range(len(allTeams)):
                    try:
                        if fuzz.ratio(allTeams[i]["team_name_short"].lower().replace(" ", ""),
                                      str(searchingName)) >= 75:
                            possible += str(allTeams[i]["team_key"]) + ", "
                            found = True
                    except AttributeError:
                        continue
            else:
                sendText(number, "That is an invalid search word. (EC3 - Overflow)")
                return True
            if found == False:
                sendText(number, "That team name was not found. Please try again")
            elif found == True:
                if ":" in raw:
                    searchingName = str(raw.split(":", 1)[1])
                else:
                    searchingName = str(raw.split(" ", 1)[1])
                sendText(number, formatResp(str(searchingName) + " could be team " + str(possible), "", 0))
        else:
            sendText(number, "That is not a valid team name")
        return True

def formatResp(strOne, strTwo, allFlag):  # Formats end response to send to user [Truncates and removes end characters]
    # str(basicInfo + advancedInfo).replace(",;",";")[:-2]
    totalStr = strOne + strTwo
    totalStr.replace(",;", ";")
    totalStr = totalStr[:-2]
    while totalStr.endswith(",") or totalStr.endswith(" "):
        totalStr = totalStr[:-1]
    if len(totalStr) >= 160 and allFlag == 1:
        totalStr = totalStr[:157] + "..."
    if len(totalStr) > 1000:
        totalStr = totalStr[:950] + "... [Information truncated due to being over 1000 characters]"
    return totalStr

def sendHelp(number, splitParts, rawRequest):  # Sends message to any admin in help list
    if "sendhelp" in splitParts:
        bannedNums = []
        with open('bannedNumbers.txt', 'r') as banFile:
            for line in banFile:
                # remove linebreak which is the last character of the string
                addBan = line[:-1]
                bannedNums.append(addBan)
        print(str(number) + " used sendHelp")
        print(str(bannedNums))
        if helpNumList and number not in bannedNums:
            sendText(number, "All admin in help list have been pinged")
            splitParts = rawRequest.lower().replace(" ", " ").split(":")
            for i in helpNumList:
                sendText(i, "Help requested from " + str(number))
                sendText(i, "From user: " + splitParts[splitParts.index("sendhelp") + 1])
        elif number in bannedNums:
            sendText(number,
                     "You have been banned from using sendHelp. Ping @Huppdo on discord in the FTC or TOA discord servers to discuss")
        else:
            sendText(number,
                     "There are no admins in the help list. Ping @Huppdo on discord in the FTC or TOA discord servers")
        return True
    else:
        return False

def liveStats(number, splitParts):
    return False
    '''if "team" in splitParts:
        if "livestats" in splitParts:
            if "ranking" in splitParts:
                rankR = requests.get(apiURL + "event/" + liveMatchKey + "/rankings", headers=apiHeaders)
                try:
                    for i in range(len(rankR.json())):
                        if rankR.json()[i]["team_key"] == splitParts[splitParts.index("team") + 1]:
                            sendText(number, "Team " + str(splitParts[splitParts.index("team") + 1]) + " is ranked " + str(rankR.json()[i]["rank"]) + " at their current event.")
                            break
                except:
                    sendText(number, "Sorry, however that information could not be found. Perhaps the rankings for this event aren't uploaded yet")
            elif "matchscores" in splitParts:
                matchR = requests.get(apiURL + "event/" + liveMatchKey + "/matches", headers=apiHeaders)
                for i in range(len(matchR.json())):
                    for a in range(len(matchR.json()[i]["participants"])):
                        if matchR.json()[i]["participants"][a]["team_key"] == splitParts[splitParts.index("team") + 1]:
                            station = matchR.json()[i]["participants"][a]["station"]
                            jsonInfo = matchR.json()[i]
                            if station == 10 or station == 11 or station == 12 or station == 13 or station == 14:
                                redStr = "Auto - " + str(jsonInfo["red_auto_score"]) + "; "
                                redStr += "TeleOP - " + str(jsonInfo["red_tele_score"]) + "; "
                                redStr += "Endgame - " + str(jsonInfo["red_end_score"]) + "; "
                                redStr += "Total - " + str(jsonInfo["red_score"]) + ""
                            else:
                                blueStr = "Auto - " + str(jsonInfo["blue_auto_score"]) + "; "
                                blueStr += "TeleOP - " + str(jsonInfo["blue_tele_score"]) + "; "
                                blueStr += "Endgame - " + str(jsonInfo["blue_end_score"]) + "; "
                                blueStr += "Total - " + str(jsonInfo["blue_score"]) + ""
            else:
                sendText(number, "Please provide a more indepth command for livestats")
            return True
    elif "livestats" in splitParts:
        if "topteams" in splitParts:
            rankR = requests.get(apiURL + "event/" + liveMatchKey + "/rankings", headers=apiHeaders)
            topTeam = "Not available"
            secTeam = "Not available"
            thirdTeam = "Not available"
            try:
                for i in range(len(rankR.json())):
                    if rankR.json()[i]["rank"] == 1:
                        topTeam = rankR.json()[i]["team_key"]
                    elif rankR.json()[i]["rank"] == 2:
                        secTeam = rankR.json()[i]["team_key"]
                    elif rankR.json()[i]["rank"] == 3:
                        thirdTeam = rankR.json()[i]["team_key"]
                sendText(number,
                         "Top ranked team - " + str(topTeam) + ", 2nd - " + str(secTeam) + ", 3rd - " + str(thirdTeam))
            except:
                sendText(number,
                         "Sorry, however that information could not be found. Perhaps the rankings for this event aren't uploaded yet")
            return True'''

def checkTeam(msg, number):  # Code run upon thread starting
    metricCount(1)
    global disableMode
    splitParts = parseRequest(number, msg)
    if optOutIn(number,splitParts) is True:
        return
    if pingList:  # Checks for numbers to send a ping to
        for adminNum in pingList:
            if adminNum != number:
                sendText(adminNum, number + " made a request")
    if checkHelp(splitParts, number) is True:  # Checks if a help request was made
        metricCount(8)
        return
    if checkAdminMsg(number, splitParts, msg) is True:  # Check if admin request was made
        return
    if playGames(number, splitParts) is True:
        return
    if sendMass(splitParts, msg, number):
        return
    if disableMode == 0:  # Checks to make sure not disabled/froze
        if avgPoints(number, splitParts) is True:  # Checks if average score was requested
            metricCount(9)
            return
        if personalizedTeam(number, splitParts):
            return
        if champsCmds(number, splitParts) or \
                sendHelp(number, splitParts, msg) or \
                addLive(number, splitParts) or \
                liveStats(number, splitParts) or \
                checkName(number, splitParts, msg):
            return

        if msg.replace(" ", "").isdigit():  # Checks for just team #
            checkOnlyTeam(msg, number)
        else:
            checkTeamFlags(splitParts, number)
    else:
        sendText(number,
                 "TOAText is currently disabled by an admin for maintenance or other reasons! Please check back later.")

def oprCheck(number, splitParts):
    if 'opr' in splitParts:
        metricCount(13)
        print(str(number) + " used the OPR command")
        r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/events/1819",
                         headers=apiHeaders)
        msgSent = False
        for i in range(len(r.json())):
            eventr = requests.get(apiURL + "event/" + r.json()[i]["event_key"] + "/rankings", headers=apiHeaders)
            namer = requests.get(apiURL + "event/" + r.json()[i]["event_key"], headers=apiHeaders)
            for a in range(len(eventr.json())):
                if eventr.json()[a]["team_key"] == splitParts[splitParts.index("team") + 1]:
                    sendText(number,"The OPR for " + str(splitParts[splitParts.index("team") + 1]) + " at " + namer.json()[0]["event_name"] + " (" + namer.json()[0]["start_date"][:10]  + ") was " + str(eventr.json()[a]["opr"]))
                    msgSent = True
                    break
        if not msgSent:
            sendText(number, "This team did not have any OPRs tied to it. Check again later")
        return True

def checkOnlyTeam(teamNum, number):  # Code for if request just has team
    r = requests.get(apiURL + "team/" + teamNum, headers=apiHeaders)
    splitParts = ['team', 'location', 'shortname', 'startyear', 'events']
    splitParts.insert(1, teamNum)
    if "_code" not in r.json():
        refDB = db.reference('Phones')
        userNum = number[1:]
        refDB.child(userNum).update({"lastTeam": str(splitParts[splitParts.index("team") + 1])})
        if liveStats(number, splitParts):
            return
        if getTeamMatches(number, splitParts):
            return
        basicInfo = checkTeamInfo(splitParts)
        advancedInfo = checkAdvInfo(splitParts)
        if advancedInfo == "" and basicInfo == "":
            returnErrorMsg("falseArg", number)
        else:
            sendText(number, formatResp(basicInfo, advancedInfo, 1))
    else:
        sendText(number, "Invalid Team Number")
        return False

def playGames(number, splitParts):  # plays flip a coin or RPS
    if "flip" in splitParts:
        print(str(number) + " Used Flip")
        results = ["Heads!", "Tails!"]
        sendText(number, rand.choice(results))
        return True
    if "rps" in splitParts:
        expressions = ["Rock", "Paper", "Scissors"]
        computerChoice = rand.randint(0, 2)
        userChoice = None
        for (i, expr) in enumerate(expressions):
            if expr.lower() in splitParts:
                userChoice = i

        if userChoice is None:
            sendText(number, "Send rps with 'rock', 'paper', or 'scissors' to play")
            return True

        print(str(number) + " Used RPS")
        # Rock = 0, Paper = 1, Scissors = 2
        # 0 beats 2, 1 beats 0, 2 beats 1
        response = "%s (you) vs %s (computer) - " % (expressions[userChoice], expressions[computerChoice])
        result = None
        if computerChoice == userChoice:
            result = "Tie"
        elif userChoice == (computerChoice + 1) % 3:
            result = "You win"
        else:
            result = "You lose"

        sendText(number, response + result)
        return True

def checkTeamFlags(splitParts, number):  # Code for if request has flags
    allFlag = 0
    if splitParts[0].isdigit() or splitParts[0] == 'team':
        if splitParts[0].isdigit():
            splitParts.insert(0, 'team')
        print(splitParts[splitParts.index("team") + 1])
        r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1], headers=apiHeaders)
        allFlag = 0
        if "_code" not in r.json():
            refDB = db.reference('Phones')
            userNum = number[1:]
            refDB.child(userNum).update({"lastTeam": str(splitParts[splitParts.index("team") + 1])})
            if len(splitParts) == 2 and splitParts[0] == 'team':
                splitParts.append('all')
            # print("Team Found")
            # print(r.text)
            if 'all' in splitParts:
                splitParts.append('location')
                splitParts.append('shortname')
                splitParts.append('startyear')
                splitParts.append('website')
                splitParts.append('events')
                allFlag = 1
            if getTeamMatches(number, splitParts):
                return
            if liveStats(number, splitParts):
                return
            if oprCheck(number, splitParts) is True:
                return
            basicInfo = checkTeamInfo(splitParts)
            advancedInfo = checkAdvInfo(splitParts)
            if advancedInfo == "" and basicInfo == "":
                returnErrorMsg("falseArg", number)
            else:
                sendText(number, formatResp(basicInfo, advancedInfo, allFlag))
        else:
            sendText(number, "Invalid Team Number")
            return False
    else:
        refDB = db.reference('Phones')
        phoneDB = refDB.order_by_key().get()
        userNum = number[1:]
        try:
            splitParts.remove("team")
        except:
            pass
        try:
            if phoneDB[str(userNum)]["lastTeam"] is not None:
                splitParts.insert(0, "team")
                splitParts.insert(1, str(phoneDB[str(userNum)]["lastTeam"]))
                if 'all' in splitParts:
                    splitParts.append('location')
                    splitParts.append('shortname')
                    splitParts.append('startyear')
                    splitParts.append('website')
                    splitParts.append('events')
                    allFlag = 1
                if getTeamMatches(number, splitParts):
                    return
                if liveStats(number, splitParts):
                    return
                if oprCheck(number, splitParts) is True:
                    return
                basicInfo = checkTeamInfo(splitParts)
                advancedInfo = checkAdvInfo(splitParts)
                if advancedInfo == "" and basicInfo == "":
                    returnErrorMsg("falseArg", number)
                else:
                    sendText(number, formatResp(basicInfo, advancedInfo, allFlag))
            else:
                returnErrorMsg('invalTeam', number)
                return False
        except:
            returnErrorMsg('invalTeam', number)
            return False

def getTeamMatches(number, splitParts):  # Code to view a teams matches
    def redcompileinfo(jsonInfo):
        redStr = "Auto - " + str(jsonInfo[0]["red_auto_score"]) + "; "
        redStr += "TeleOP - " + str(jsonInfo[0]["red_tele_score"]) + "; "
        redStr += "Endgame - " + str(jsonInfo[0]["red_end_score"]) + "; "
        redStr += "Total - " + str(jsonInfo[0]["red_score"]) + " @ "
        eventR = requests.get(apiURL + "event/" + str(jsonInfo[0]["event_key"]),
                              headers=apiHeaders)
        redStr += eventR.json()[0]["event_name"]
        if len(redStr) >= 160:
            redStr = redStr[:155] + "..."
        return redStr
    def bluecompileinfo(jsonInfo):
        blueStr = "Auto - " + str(jsonInfo[0]["blue_auto_score"]) + "; "
        blueStr += "TeleOP - " + str(jsonInfo[0]["blue_tele_score"]) + "; "
        blueStr += "Endgame - " + str(jsonInfo[0]["blue_end_score"]) + "; "
        blueStr += "Total - " + str(jsonInfo[0]["blue_score"]) + " @ "
        eventR = requests.get(apiURL + "event/" + str(jsonInfo[0]["event_key"]),
                              headers=apiHeaders)
        blueStr += eventR.json()[0]["event_name"]
        if len(blueStr) >= 160:
            blueStr = blueStr[:155] + "..."
        return blueStr

    if "matchinfo" in splitParts:
        metricCount(11)
        try:
            if splitParts[splitParts.index("team") + 2] == "matchinfo" and splitParts[
                splitParts.index("team") + 3] == "matches":
                print(str(number) + "got a team's matches")
                r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/matches/1819",
                                 headers=apiHeaders)
                matchStr = "Matches with " + str(splitParts[splitParts.index("team") + 1]) + "-    "
                for i in range(len(r.json())):
                    matchStr += str(r.json()[i]["match_key"]) + ", "
                sendText(number, formatResp(matchStr, "", 0))
            elif splitParts[splitParts.index("team") + 2] == "matchinfo" and "1819" in splitParts[
                splitParts.index("team") + 3]:
                print(str(number) + "got a match info")
                r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/matches/1819",
                                 headers=apiHeaders)
                station = -1
                for i in range(len(r.json())):
                    if r.json()[i]["match_key"].lower() == splitParts[splitParts.index("team") + 3]:
                        station = r.json()[i]["station"]
                matchR = requests.get(apiURL + "match/" + splitParts[splitParts.index("team") + 3], headers=apiHeaders)
                matchStr = "Match info : "
                if station == 10 or station == 11 or station == 12 or station == 13 or station == 14:
                    matchStr = redcompileinfo(matchR.json())
                else:
                    matchStr = bluecompileinfo(matchR.json())
                if station == -1:
                    sendText(number, "The requested team was not in the match or is missing info")
                else:
                    sendText(number, formatResp(matchStr, "", 0))
            elif splitParts[splitParts.index("team") + 2] == "matchinfo" and splitParts[
                splitParts.index("team") + 3] == "minmax":
                print(str(number) + "got a teams worst and best match (minMax)")
                minMatch = ""
                maxMatch = ""
                minStation = 0
                maxStation = 0
                minScore = 500
                maxScore = 0
                station = -1
                r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/matches/1819",
                                 headers=apiHeaders)
                for i in range(len(r.json())):
                    station = r.json()[i]["station"]
                    matchR = requests.get(apiURL + "match/" + r.json()[i]["match_key"], headers=apiHeaders)
                    if station == 10 or station == 11 or station == 12 or station == 13 or station == 14:
                        if matchR.json()[0]["red_score"] > maxScore:
                            maxMatch = r.json()[i]["match_key"]
                            maxScore = matchR.json()[0]["red_score"]
                            maxStation = r.json()[i]["station"]
                        if matchR.json()[0]["red_score"] < minScore:
                            minMatch = r.json()[i]["match_key"]
                            minScore = matchR.json()[0]["red_score"]
                            minStation = r.json()[i]["station"]
                    else:
                        if matchR.json()[0]["blue_score"] > maxScore:
                            maxMatch = r.json()[i]["match_key"]
                            maxScore = matchR.json()[0]["blue_score"]
                            maxStation = r.json()[i]["station"]
                        if matchR.json()[0]["blue_score"] < minScore:
                            minMatch = r.json()[i]["match_key"]
                            minScore = matchR.json()[0]["blue_score"]
                            minStation = r.json()[i]["station"]
                matchR = requests.get(apiURL + "match/" + minMatch, headers=apiHeaders)
                matchStr = "Worst game: "
                if minStation == 10 or minStation == 11 or minStation == 12 or minStation == 13 or minStation == 14:
                    matchStr += redcompileinfo(matchR.json())
                else:
                    matchStr += bluecompileinfo(matchR.json())
                sendText(number, matchStr)
                matchR = requests.get(apiURL + "match/" + maxMatch, headers=apiHeaders)
                matchStr = "Best game: "
                if maxStation == 10 or maxStation == 11 or maxStation == 12 or maxStation == 13 or maxStation == 14:
                    matchStr += redcompileinfo(matchR.json())
                else:
                    matchStr += bluecompileinfo(matchR.json())
                sendText(number, matchStr)
            elif splitParts[splitParts.index("team") + 2] == "matchinfo" and splitParts[
                splitParts.index("team") + 3] == "topthree":
                print(str(number) + "got a team's best 3 matches (topThree)")
                topMatch = ""
                sndMatch = ""
                thirdMatch = ""
                topScore = 0
                sndScore = 0
                thirdScore = 0
                topStation = 0
                sndStation = 0
                thirdStation = 0
                r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/matches/1819",
                                 headers=apiHeaders)
                for i in range(len(r.json())):
                    station = r.json()[i]["station"]
                    matchR = requests.get(apiURL + "match/" + r.json()[i]["match_key"], headers=apiHeaders)
                    # print(r.json()[i]["match_key"])
                    if station == 10 or station == 11 or station == 12 or station == 13 or station == 14:
                        if matchR.json()[0]["red_score"] > topScore:
                            thirdMatch = sndMatch
                            thirdScore = sndScore
                            thirdStation = sndStation
                            sndMatch = topMatch
                            sndScore = topScore
                            sndStation = topStation
                            topMatch = r.json()[i]["match_key"]
                            topScore = matchR.json()[0]["red_score"]
                            topStation = r.json()[i]["station"]
                        elif matchR.json()[0]["red_score"] > sndScore:
                            thirdMatch = sndMatch
                            thirdScore = sndScore
                            thirdStation = sndStation
                            sndMatch = r.json()[i]["match_key"]
                            sndScore = matchR.json()[0]["red_score"]
                            sndStation = r.json()[i]["station"]
                        elif matchR.json()[0]["red_score"] > thirdScore:
                            thirdMatch = r.json()[i]["match_key"]
                            thirdScore = matchR.json()[0]["red_score"]
                            thirdStation = r.json()[i]["station"]
                    else:
                        if matchR.json()[0]["blue_score"] > topScore:
                            thirdMatch = sndMatch
                            thirdScore = sndScore
                            thirdStation = sndStation
                            sndMatch = topMatch
                            sndScore = topScore
                            sndStation = topStation
                            topMatch = r.json()[i]["match_key"]
                            topScore = matchR.json()[0]["blue_score"]
                            topStation = r.json()[i]["station"]
                        elif matchR.json()[0]["blue_score"] > sndScore:
                            thirdMatch = sndMatch
                            thirdScore = sndScore
                            thirdStation = sndStation
                            sndMatch = r.json()[i]["match_key"]
                            sndScore = matchR.json()[0]["blue_score"]
                            sndStation = r.json()[i]["station"]
                        elif matchR.json()[0]["blue_score"] > thirdScore:
                            thirdMatch = r.json()[i]["match_key"]
                            thirdScore = matchR.json()[0]["blue_score"]
                            thirdStation = r.json()[i]["station"]
                matchR = requests.get(apiURL + "match/" + topMatch, headers=apiHeaders)
                matchStr = "Top game: "
                if topMatch != "":
                    if topStation == 10 or topStation == 11 or topStation == 12 or topStation == 13 or topStation == 14:
                        matchStr += redcompileinfo(matchR.json())
                    else:
                        matchStr += bluecompileinfo(matchR.json())
                    sendText(number, matchStr)
                if sndMatch != "":
                    matchR = requests.get(apiURL + "match/" + sndMatch, headers=apiHeaders)
                    matchStr = "2nd best game: "
                    if sndStation == 10 or sndStation == 11 or sndStation == 12 or sndStation == 13 or sndStation == 14:
                        matchStr += redcompileinfo(matchR.json())
                    else:
                        matchStr += bluecompileinfo(matchR.json())
                    sendText(number, matchStr)
                if thirdMatch != "":
                    matchR = requests.get(apiURL + "match/" + thirdMatch, headers=apiHeaders)
                    matchStr = "3rd best game: "
                    if thirdStation == 10 or thirdStation == 11 or thirdStation == 12 or thirdStation == 13 or thirdStation == 14:
                        matchStr += redcompileinfo(matchR.json())
                    else:
                        matchStr += bluecompileinfo(matchR.json())
                    sendText(number, matchStr)
            else:
                sendText(number,
                         "Incorrect format. Use ?:matchinfo or helpme:matchinfo for information on how to use this command")
        except IndexError:
            sendText(number,
                     "Incorrect format. Use ?:matchinfo or helpme:matchinfo for information on how to use this command")
        return True

def checkTeamInfo(splitParts):  # Code to request basic team info
    print(splitParts)
    r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1], headers=apiHeaders)
    basicInfoString = ""
    if 'location' in splitParts:
        metricCount(2)
        if r.json()[0]["city"] and r.json()[0]["state_prov"] is not None:
            basicInfoString += "Loc. - "
            basicInfoString += r.json()[0]["city"]
            basicInfoString += ", "
            basicInfoString += r.json()[0]["state_prov"]
            basicInfoString += "; "
        else:
            basicInfoString += "Location Unknown; "
    if 'name' in splitParts:
        metricCount(3)
        basicInfoString += "Name - "
        if r.json()[0]["team_name_short"] is not None and r.json()[0]["team_name_short"] is not None:
            basicInfoString += r.json()[0]["team_name_short"]
            basicInfoString += ", "
            basicInfoString += r.json()[0]["team_name_long"]
            basicInfoString += "; "
        elif r.json()[0]["team_name_long"] is not None:
            basicInfoString += "Name - "
            basicInfoString += r.json()[0]["team_name_long"]
            basicInfoString += "; "
        else:
            basicInfoString += "Name not listed; "
    if 'shortname' in splitParts:
        metricCount(3)
        if r.json()[0]["team_name_short"] is not None:
            basicInfoString += "Name - "
            basicInfoString += r.json()[0]["team_name_short"]
            basicInfoString += "; "
        elif r.json()[0]["team_name_long"] is not None:
            basicInfoString += "Name - "
            basicInfoString += r.json()[0]["team_name_long"]
            basicInfoString += "; "
        else:
            basicInfoString += "Name not listed; "
    if 'startyear' in splitParts:
        metricCount(4)
        if r.json()[0]["rookie_year"] is not None:
            basicInfoString += "Rookie Year - "
            basicInfoString += str(r.json()[0]["rookie_year"])
            basicInfoString += "; "
        else:
            basicInfoString += "Start Year Unknown; "
    if 'website' in splitParts:
        metricCount(5)
        if r.json()[0]["website"] is not None:
            basicInfoString += "Website - "
            basicInfoString += r.json()[0]["website"]
            basicInfoString += "; "
        else:
            basicInfoString += "No Website; "
    # print(basicInfoString)
    return basicInfoString

def checkAdvInfo(splitParts):  # Code to request advanced team info
    advInfoString = ""
    if 'events' in splitParts:
        metricCount(6)
        r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/events/1819",
                         headers=apiHeaders)
        # print(r.text)
        advInfoString += "Events - "
        for i in r.json():
            # print(r.json()[r.json().index(i)]["event_key"])
            eventr = requests.get(apiURL + "event/" + r.json()[r.json().index(i)]["event_key"], headers=apiHeaders)
            advInfoString += eventr.json()[0]["event_name"] + ", "
            # print(eventr.json()[0]["event_name"])
        advInfoString += "; "
    if 'awards' in splitParts:
        metricCount(7)
        r = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/awards/1819",
                         headers=apiHeaders)
        # print(r.text)
        advInfoString += "Awards - "
        prevevent_name = ""
        firstRun = True
        addFinal = False
        loopCount = 0
        for i in r.json():
            loopCount += 1
            print(r.json()[r.json().index(i)]["award_name"])
            eventr = requests.get(apiURL + "event/" + r.json()[r.json().index(i)]["event_key"], headers=apiHeaders)
            if prevevent_name != eventr.json()[0]["event_name"] and firstRun == False:
                advInfoString += r.json()[r.json().index(i)]["award_name"] + " @ " + prevevent_name + " || "
                prevevent_name = eventr.json()[0]["event_name"]
                addFinal = False
            else:
                firstRun = False
                advInfoString += r.json()[r.json().index(i)]["award_name"] + ", "
                prevevent_name = eventr.json()[0]["event_name"]
                addFinal = True
            # advInfoString += r.json()[r.json().index(i)]["award_name"] + " @ " + eventr.json()[0]["event_name"] + ", "
        if addFinal == True:
            advInfoString = advInfoString[:-2] + " @ " + prevevent_name
        advInfoString += "; "
    if 'avgpoints' in splitParts or 'avgscore' in splitParts:
        metricCount(10)
        eventr = requests.get(apiURL + "team/" + splitParts[splitParts.index("team") + 1] + "/matches/1819",
                              headers=apiHeaders)

        eventsList = eventr.json()
        autoTeamSum = 0
        teleOpTeamSum = 0
        filledEvents = 0
        for i in range(len(eventsList)):
            print(eventsList[i]["match_key"])
            matchr = requests.get(apiURL + "match/" + eventsList[i]["match_key"], headers=apiHeaders)
            matchList = matchr.json()
            addToAuto = 0
            addToTele = 0
            for a in range(len(matchList)):
                if eventsList[i]["station"] == 10 or eventsList[i]["station"] == 11 or eventsList[i]["station"] == 12 or \
                        eventsList[i]["station"] == 13 or eventsList[i]["station"] == 14:
                    addToAuto += (matchList[a]["red_auto_score"])
                    addToTele += (matchList[a]["red_tele_score"])
                    addToTele += (matchList[a]["red_end_score"])
                else:
                    addToAuto += (matchList[a]["blue_auto_score"])
                    addToTele += (matchList[a]["blue_tele_score"])
                    addToTele += (matchList[a]["blue_end_score"])
                filledEvents += 1
                print(str(filledEvents))
                autoTeamSum += addToAuto
                teleOpTeamSum += addToTele
        advInfoString += "Avg Auto - " + str(round(autoTeamSum / filledEvents, 2)) + " || "
        advInfoString += "Avg TeleOp - " + str(round(teleOpTeamSum / filledEvents, 2)) + " || "
        advInfoString += "Avg total - " + str(
            round(autoTeamSum / filledEvents + teleOpTeamSum / filledEvents, 2)) + "; "
    return advInfoString

def checkAdminMsg(number, msg, rawRequest):  # Code for admin commands
    global disableMode
    global pingList
    global autoSum
    global teleOpSum
    global helpNumList
    if number in adminList:
        if "freeze" in msg:  # Disable or enable
            print("Admin " + str(number) + " used the freeze command")
            if disableMode == 0:
                disableMode = 1
                sendText(number, "Disable mode Enabled!")
                print("Disable mode - on")
            else:
                disableMode = 0
                sendText(number, "Disable mode Disabled!")
                print("Disable mode - off")
            return True
        elif "updateadmins" in msg:
            print("Admin " + str(number) + " used the updateAdmins command")
            loadAdminList()
            return True
        elif "checkstatus" in msg:
            print("Admin " + str(number) + " used the checkStatus command")
            sendText(number, "TOAText is online and you are on the admin list!")
            return True
        elif "pingme" in msg:
            print("Admin " + str(number) + " used the pingme command")
            if number in pingList:
                pingList.remove(number)
                sendText(number, "Removed from ping list")
            elif number not in pingList:
                pingList.append(number)
                sendText(number, "Added to ping list")
            return True
        elif "joinhelp" in msg:
            print("Admin " + str(number) + " used the joinHelp command")
            if number in helpNumList:
                helpNumList.remove(number)
                sendText(number, "Removed from help list")
            elif number not in helpNumList:
                helpNumList.append(number)
                sendText(number, "Added to help list")
            return True
        elif "sendhelp" in msg:
            print("Admin " + str(number) + " used the sendHelp command")
            splitParts = rawRequest.lower().replace(" ", " ").split(":")
            sendText(str(splitParts[1]), "From admin - " + str(splitParts[2]))
            return True
        elif "serverstatus" in msg or "ss" in msg:
            r = requests.get(functionsURL + "serverStatus", headers=functionsHeaders)
            resp = r.json()
            totalStatus = ""
            for x in range(len(resp)):
                procName = resp[x]["name"]
                procID = resp[x]["pm_id"]
                procStat = resp[x]["pm2_env"]["status"]
                totalStatus += str(procName) + "(" + str(procID) + ") is " + str(procStat) + "; "
            sendText(number, formatResp(str(totalStatus), "", 0))
            return True
        elif "banhelp" in msg:
            print("Admin " + str(number) + " used the banHelp command")
            bannedNums = []
            with open('bannedNumbers.txt', 'r') as banFile:
                for line in banFile:
                    # remove linebreak which is the last character of the string
                    addBan = line[:-1]
                    bannedNums.append(addBan)
            bannedNums.append(msg[msg.index("banhelp") + 1])
            with open('bannedNumbers.txt', 'w') as banFile:
                for bannedNumber in bannedNums:
                    banFile.write('%s\n' % bannedNumber)
            return True
        elif "updateavg" in msg:
            print("Admin " + str(number) + " used the updateavg command")
            null = None
            false = False
            true = True
            eventr = requests.get(apiURL + "event/?season_key=1819", headers=apiHeaders)
            eventsList = eventr.json()
            autoSum = 0
            teleOpSum = 0
            filledEvents = 0
            for i in range(len(eventsList)):
                if "2019-03-09" in eventsList[i]["start_date"]:
                    print(eventsList[i]["event_name"])
                    matchr = requests.get(apiURL + "event/" + eventsList[i]["event_key"] + "/matches",
                                          headers=apiHeaders)
                    matchList = matchr.json()
                    addToAuto = 0
                    addToTele = 0
                    for a in range(len(matchList)):
                        addToAuto += ((matchList[a]["red_auto_score"] + matchList[a]["blue_auto_score"]) / 2)
                        addToTele += ((matchList[a]["red_tele_score"] + matchList[a]["blue_tele_score"] + matchList[a][
                            "red_end_score"] + matchList[a]["blue_end_score"]) / 4)
                    if len(matchList) != 0:
                        filledEvents += 1
                        autoSum += addToAuto / len(matchList)
                        teleOpSum += addToTele / len(matchList)
            autoSum = autoSum / filledEvents
            teleOpSum = teleOpSum / filledEvents
            print("Average auto score - " + str(autoSum) + " || Average TeleOp score - " + str(
                teleOpSum) + " || Average score - " + str(autoSum + teleOpSum))
            return True
    if number in eventAdminList:
        if "metrics" in msg or "metrix" in msg:
            print("Admin " + str(number) + " used the metrics command")
            sendText(number, metricGet())
            return True
        elif "metrics2" in msg or "metrix2" in msg:
            print("Admin " + str(number) + " used the metrics2 command")
            sendText(number, metricTwoGet())
            return True
    else:
        return False

def metricCount(action):  # Code to log metrics
    with open("metric.json", "r") as read_file:
        data = json.load(read_file)
    metricList = ["textsRec", "locGet", "nameGet", "yearGet", "webGet", "eveGet", "awardGet", "helpGet", "avgTotalGet","avgGet",
                  "matchGet", "livesSent", "oprGet"]
    data[str(metricList[action - 1])] += 1
    with open("metric.json", "w") as write_file:
        json.dump(data, write_file)

def metricGet():  # Retrieves metrics
    with open("metric.json", "r") as read_file:
        data = json.load(read_file)
    metricStr = ""
    metricStr += "Texts received - " + str(data["textsRec"]) + "; "
    metricStr += "Location reqs - " + str(data["locGet"]) + "; "
    metricStr += "Name reqs - " + str(data["nameGet"]) + "; "
    metricStr += "Start Year reqs - " + str(data["yearGet"]) + "; "
    metricStr += "Website reqs - " + str(data["webGet"]) + "; "
    metricStr += "Event reqs - " + str(data["eveGet"]) + "; "
    metricStr += "Award reqs - " + str(data["awardGet"])
    return metricStr

def metricTwoGet():  # Retrieves metrics
    with open("metric.json", "r") as read_file:
        data = json.load(read_file)
    metricStr = ""
    metricStr += "Help requests - " + str(data["helpGet"]) + "; "
    metricStr += "TotalAvg reqs - " + str(data["avgTotalGet"]) + "; "
    metricStr += "TeamAvg reqs - " + str(data["avgGet"]) + "; "
    metricStr += "Match info reqs - " + str(data["matchGet"]) + "; "
    metricStr += "Live Alerts sent - " + str(data["livesSent"]) + "; "
    metricStr += "OPR reqs - " + str(data["oprGet"])
    return metricStr

def loadAdminList():  # Loads admin numbers off admin.json
    global adminList
    global eventAdminList
    adminList = []
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    userDB = db.reference('Users')
    levelDB = userDB.order_by_key().get()
    for number in phoneDB:
        try:
            if phoneDB[number]['uid']:
                if levelDB[phoneDB[number]['uid']]['level'] == 6:
                    adminList.append("+"+number)
            else:
                continue
        except:
            continue
    print(adminList)
    eventAdminList = adminList

def loadAPIKeys():  # Loads Twilio account info off twilio.json
    global twilioAuth
    global twilioAccountID
    global apiHeaders
    global functionsHeaders
    global webhookKey
    with open("twilio.json", "r") as read_file:
        data = json.load(read_file)
    twilioAuth = str(data["twilioAuth"])
    twilioAccountID = str(data["twilioID"])
    apiHeaders = {'content-type': 'application/json',
                  'X-TOA-KEY': str(data["toaKey"]),
                  'X-Application-Origin': 'TOAText'}
    functionsHeaders = {'Authorization': str(data["functionKey"])}
    webhookKey = str(data["webhookKey"])

def loadAllTeams():  # Requests list of all teams to be stored for string matching
    global allTeams
    print("All teams requested")
    teamsR = requests.get(apiURL + "team/",
                          headers=apiHeaders)
    allTeams = teamsR.json()
    print("Recieved all teams")

def personalizedTeam(number, splitParts):
    if "mytoa" in splitParts:
        print("User used myTOA command")
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
                    levelDefinitions = ["General User", "Team/Event Admin", "Regional Admin", "FIRST", "Moderator", "Admin"]
                    if int(userSortDB[UID]["level"]) != 1:
                        firstMsg += ". Also, you have an account level of " + str(userSortDB[UID]["level"]) + " (" + levelDefinitions[int(userSortDB[UID]["level"]) - 1] + ")"
                except:
                    firstMsg += ""
                sendText(number, firstMsg)
            else:
                print("That user exists and has no user ID")
        except:
            sendText(number, "Your phone number has not been linked to a myTOA profile (EC4)")
            return True
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
            sendText(number, teamStr)
        else:
            sendText(number, "You have not set any favorite teams in your myTOA profile!")
        return True

def sendMass(splitParts, rawMsg, requester):
    if "massmsg" in splitParts and requester in adminList:
        refDB = db.reference('Phones')
        phoneDB = refDB.order_by_key().get()
        for number in phoneDB:
            try:
                sendText("+" + number, rawMsg.replace("massmsg ", ""), False)
            except:
                print("Failed on " + number)
        return True
    elif "eventmsg" in splitParts and requester in adminList:
        try:
            refDB = db.reference('liveEvents')
            eventsDB = refDB.order_by_key().get()
            userMsg = rawMsg.replace("eventmsg", "")
            userMsg = userMsg.split(" ", 2)[2]
            while userMsg[0] == " ":
                userMsg = userMsg[1:]
            for attendeeNum in eventsDB[str(splitParts[splitParts.index("eventmsg") + 1]).upper()].keys():
                userNum = "+" + attendeeNum
                sendText(str(userNum), str(userMsg), False)
            print(userMsg)
            return True
        except KeyError:
            sendText(requester, "This eventmsg was not sent!")
            return True
        except ValueError:
            sendText(requester, "This eventmsg was not sent!")
            return True
        except AttributeError:
            sendText(requester, "This eventmsg was not sent!")
            return True

def optOutIn(userNum, splitParts):
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    number = userNum
    userNum = userNum[1:]
    if userNum not in phoneDB:
        refDB.child(userNum).set({'opted': True})
        print("Phone number added to DB")
        refDB = db.reference('Phones')
        phoneDB = refDB.order_by_key().get()
    if "quit" in splitParts or "stop" in splitParts:
        refDB.child(userNum).update({'opted': False})
        sendText(number, "You have now opted out of ALL TOAText messages. Send START to rejoin", True)
        print(str(userNum) + " has opted out")
        return True
    elif "start" in splitParts:
        refDB.child(userNum).update({'opted': True})
        sendText(number, "You have now rejoined TOAText and can use all the features")
        return True
    if not phoneDB[userNum]['opted']:
        print("An opted out user (" + str(number) + ") has tried to make a request")
        return True
    else:
        return False

if __name__ == "__main__":  # starts the whole program
    print("started")
    loadAdminList()
    loadAPIKeys()
    loadAllTeams()
    checkAdminMsg(str(adminList[0]), ["updateavg", "startup"], "")  # Does a update for the averages upon boot
    for num in adminList:
        if "740" in num:
            sendText(str(num), str(adminList), True)
    app.run(host='0.0.0.0', port=5001)