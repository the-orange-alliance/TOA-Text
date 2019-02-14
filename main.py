import requests
from twilio import twiml
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import random as rand
import threading
import json
import time
from flask import Flask, request
from fuzzywuzzy import fuzz
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

cred = credentials.Certificate('TOAFirebase.json')
default_app = firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://dev-db-the-orange-alliance-30064.firebaseio.com/'
})

app = Flask(__name__)
apiURL = "http://35.202.99.121/api/"

apiHeaders = {'content-type': 'application/json',
              'X-TOA-KEY': '',
              'X-Application-Origin': 'TOAText'}

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

# global val for average comp last weekend
autoSum = 0
teleOpSum = 0

#list of numbers who want to use the 810 number
numTwoList = []


#all of live channel 1 variables
liveScoreRunning = False
liveMatchKey = ""
liveScoreList = []
liveScorePredict = []
liveScoreScores = []
liveSkip = False
liveQualMode = False

#all of live channel 2 variables
liveScoreRunningTwo = False
liveMatchKeyTwo = ""
liveScoreListTwo = []
liveSkipTwo = False
liveQualModeTwo = False

#all of live channel 3 variables
liveScoreRunningThree = False
liveMatchKeyThree = ""
liveScoreListThree = []
liveSkipThree = False
liveQualModeThree = False

#FTCScores live scoring
FTCScoresRunning = False
FTCScoresMatchKey = ""
FTCScoresList = []

mainNum = ""
secNum = ""
class myThread(threading.Thread):  # Thread created upon request
    def __init__(self, name, sendnum, msgbody):
        threading.Thread.__init__(self)
        self.name = name
        self.sendnum = sendnum
        self.msgbody = msgbody

    def run(self):
        print("Fetching request to " + self.sendnum)
        checkTeam(self.msgbody, self.sendnum)
        print("Finished request to " + self.sendnum)


class liveScoringThread(threading.Thread):  # Thread created for live scoring channel 1
    def __init__(self, name, startingUser):
        threading.Thread.__init__(self)
        self.name = name
        self.startingUser = startingUser

    def run(self):
        print("Starting live scoring")
        checkLiveScoring()
        sendText(self.startingUser, "Live scoring has shut down successfully")
        print("Live scoring ended")


class liveScoringThreadTwo(threading.Thread):  # Thread created for live scoring channel 2
    def __init__(self, name, startingUser):
        threading.Thread.__init__(self)
        self.name = name
        self.startingUser = startingUser

    def run(self):
        print("Starting live scoring Two")
        checkLiveScoringTwo()
        sendText(self.startingUser, "Live scoring 2 has shut down successfully")
        print("Live scoring ended Two")


class liveScoringThreadThree(threading.Thread):  # Thread created for live scoring channel 3
    def __init__(self, name, startingUser):
        threading.Thread.__init__(self)
        self.name = name
        self.startingUser = startingUser
    def run(self):
        print("Starting live scoring Three")
        checkLiveScoringThree()
        sendText(self.startingUser, "Live scoring 3 has shut down successfully")
        print("Live scoring ended Three")

class FTCScoresThread(threading.Thread):  # Thread created for FTCScores
    def __init__(self, name, startingUser):
        threading.Thread.__init__(self)
        self.name = name
        self.startingUser = startingUser
    def run(self):
        print("Starting live scoring FTCScores")
        checkLiveScoringFTCScores()
        sendText(self.startingUser, "Live scoring FTCScores has shut down successfully")
        print("Live scoring ended FTCScores")


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
    t = myThread(number, number, message_body)
    t.start()
    return (str(resp))


def sendText(number, msg):  # Code to send outgoing text
    global numTwoList
    account_sid = twilioAccountID
    auth_token = twilioAuth
    client = Client(account_sid, auth_token)
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
    "startYear": "responds with a team's rookie year",
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
                 "Use format [team#]:livestats:matches to return all matches a team has played in",
    "sendhelp": "pings admins in help list with your number and issue",
    "avgtotalscore": "responds with average auto and teleOp scores for previous weekend",
    "avgtotalpoints": "responds with average auto and teleOp scores for previous weekend",
    "addlive": "toggles whether a user is receiving live text notifications for the currently selected game",
    "checklives": "shows what events are currently using live scoring",
    "addlive2": "toggles whether a user is receiving live text notifications for the currently selected game, channel 2 is less in-depth",
    "avgscore": "responds with approx. average score for the alliances a team has been on",
    "avgpoints": "responds with approx. average score for the alliances a team has been on"
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
    defaultSend = 0
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
                     "Available team requests are: location, name, startYear, website, events, awards, avgScore, matchinfo, livestats")
            sendText(number,
                     "Available non-team requests are: avgTotalScore, about, sendhelp, newCMDs, addLive, flip, checklives, searchTN")
            adminHelpStr = ""
            if number in adminList:
                adminHelpStr += "Admin requests: checkStatus, freeze, metrics, metrics2, pingme, updateavg, joinhelp, sendhelp, updateAdmins; "
            if number in eventAdminList:
                adminHelpStr += "Event requests: toggleLive, liveskip, livequalmode"
                sendText(number, adminHelpStr)
            sendText(number,
                     "Example - 15692:location:name:events or 15692 shortname awards. If you're still confused, use ?:[command] to know more")
            sendText(number,
                     "Text STOP to opt-out of using TOAText. Use START to opt back into TOAText.")
        return True
    elif "about" in splitParts:
        sendText(number,
                 "TOAText is a portable, on-the-go version of The Orange Alliance. It can provide information about teams, along with statistics")
        sendText(number, "Created by Team 15692 in collaboration with The Orange Alliance. Special thanks to Dominic Hupp for maintaining this project")
        sendText(number, "To know more about any commands, use ?:[command] or helpme:[command]")
        return True
    elif "newcmds" in splitParts:
        sendText(number, "New features - checklives, livestats, matchinfo, addLive, searchTN")
        return True
    elif "pickup" in splitParts:
        returnErrorMsg("valDay", number)
        print("User used pickup command")
        return True
    elif "checklives" in splitParts:
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
        sendText(number, str(runningKeys))
        return True
    else:
        return False


def advertsCheck(number, splitParts):
    '''if "robotlib" in splitParts:
    sendText(number, "Need a library for more effectively programming FTC robots? Go to: https://github.com/jdroids/robotlib")
    return True'''


def avgPoints(number, splitParts):  # Average total points
    if "avgtotalscore" in splitParts or "avgtotalpoints" in splitParts:
        print(number + " requested average score")
        sendText(number, "Average auto score - " + str(round(autoSum, 2)) + " || Average TeleOp score - " + str(
            round(teleOpSum, 2)) + " || Average score - " + str(round(float(autoSum + teleOpSum), 2)))
        return True


def addLive(number, splitParts):  # Adds users to live alert threads One, Two, or Three
    if "addlive" in splitParts:
        print(str(number) + " Used AddLive")
        if number in liveScoreList:
            del liveScoreScores[liveScoreList.index(number)]
            del liveScorePredict[liveScoreList.index(number)]
            liveScoreList.remove(number)
            sendText(number, "You have been removed from the live scoring alerts")
        elif number not in liveScoreList:
            liveScoreList.append(number)
            liveScorePredict.append(0)
            liveScoreScores.append(0)
            sendText(number, "You have been added to the live scoring alerts. Send addLive again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    if "addlive2" in splitParts:
        print(str(number) + " Used AddLive2")
        if number in liveScoreListTwo:
            liveScoreListTwo.remove(number)
            sendText(number, "You have been removed from the live scoring alerts")
        elif number not in liveScoreListTwo:
            liveScoreListTwo.append(number)
            sendText(number, "You have been added to the live scoring alerts. Send addLive2 again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
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
    if "addlive3" in splitParts:
        print(str(number) + " Used AddLive3")
        if number in liveScoreListThree:
            liveScoreListThree.remove(number)
            sendText(number, "You have been removed from the live scoring alerts")
        elif number not in liveScoreListThree:
            liveScoreListThree.append(number)
            sendText(number, "You have been added to the live scoring alerts. Send addLive2 again to be removed")
            sendText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    if "predict" in splitParts and number in liveScoreList:
        print(str(number) + " Used predict")
        if splitParts[splitParts.index("predict") + 1] == "red":
            liveScorePredict[liveScoreList.index(str(number))] = 1
        elif splitParts[splitParts.index("predict") + 1] == "blue":
            liveScorePredict[liveScoreList.index(str(number))] = 2
        return True
    elif "predict" in splitParts:
        print(str(number) + " Used predict")
        sendText(number, "You must be in a live scoring queue to predict the match")
        return True
    if "getscore" in splitParts and number in liveScoreList:
        print(str(number) + " Used getscore")
        sendText(number, "Your current score is: " + str(liveScoreScores[liveScoreList.index(str(number))]))
        return True
    elif "getscore" in splitParts:
        print(str(number) + " Used getscore")
        sendText(number, "You must be in a live scoring queue to get your prediction score")
        return True


def returnErrorMsg(error, number):  # Error messages
    errorMsgText = "Hey there! Thats not very nice of you! (ECU)"
    '''errorList = ["Whoops. Someone must've forgotten to use a grounding strap!", "This is really grinding my gears",
             "I must be a swerve drive, because apparently I never work!", "Hey there! Thats not very nice of you!",
             "Just remember, goBILDA or go home", "... Bestrix.",
             "Hold your horses, that's not very GP of you",
             "Try again. The delivery robot strafed the wrong direction",
             "I'm still waiting... and waiting... and waiting"]'''
    errorList = ["Baby, are you FTC? Because everyone overlooks you and they shouldn't", "Are you a tank drive? Cause I'd pick you every time",
                 "Are you a rivet, because without you I'd fall apart", "Don't call me Java, because I'll never treat you like an object",
                 "Baby are you a swerve drive 'cause you spin me right round", "Are you a compass?  Because you're a-cute and I love having you around",
                 "Hey baby, are you a soldering iron because I melt when I see you", "You're FIRST in my heart", "Are you FTC? Because I'll care about you when nobody else will",
                 "Are you a robot, cause you just drove away with my heart", "Not in elims? You're always the first seed in my heart!!",
                 "Are you hook and loop tape? Because I think I'm stuck on you", "Are you the end game of Rover Ruckus, because I just wanna hang out",
                 "Are you a mineral? Cause picking you up is my goal"]
    randomNum = rand.randint(0, len(errorList)-1)
    errorMsgText = errorList[randomNum]
    if error == 'invalTeam':  # Missing Team Arguement
        errorMsgText += " (EC1)"
    if error == 'falseArg':  # Uses only unreal args
        errorMsgText += " (EC2)"
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
                sendText(number, formatResp(str(searchingName) + " could be team " + str(possible[:-2]), "", 0))
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
    if "team" in splitParts:
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
            return True

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
    if disableMode == 0:  # Checks to make sure not disabled/froze
        if avgPoints(number, splitParts) is True:  # Checks if average score was requested
            metricCount(9)
            return

        if advertsCheck(number, splitParts) or \
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


def checkOnlyTeam(teamNum, number):  # Code for if request just has team #
    r = requests.get(apiURL + "team/" + teamNum, headers=apiHeaders)
    splitParts = ['team', 'location', 'shortname', 'startyear', 'events']
    splitParts.insert(1, teamNum)
    if "_code" not in r.json():
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
        returnErrorMsg('invalTeam', number)
        return False


def checkLiveScoring():  # live scoring channel 1
    global liveMatchKey
    global liveScoreList
    global liveScoreRunning
    global liveScorePredict
    global liveScoreScores
    global liveSkip
    liveSkip = False
    currentMatch = 1
    r = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q00" + str(currentMatch) + "-1",
                     headers=apiHeaders)
    while liveScoreRunning:  # Keeps it running if no match schedule has been uploaded
        time.sleep(5)
        r = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q00" + str(currentMatch) + "-1",
                         headers=apiHeaders)
        print("Waiting for schedule")
        if "_code" not in r.json():
            break
    while liveScoreRunning:
        time.sleep(10)
        if liveSkip:
            liveSkip = False
            currentMatch += 1
        try:
            if currentMatch < 10:
                r = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q00" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKey) + "-Q00" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            elif currentMatch < 100:
                r = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q0" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKey) + "-Q0" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            if r.json()[0]["red_score"] is not None and r.json()[0]["blue_score"] is not None:
                if r.json()[0]["red_score"] > 0 or r.json()[0]["blue_score"] > 0:
                    redOne = ""
                    redTwo = ""
                    blueOne = ""
                    blueTwo = ""
                    for i in range(len(personR.json())):
                        if personR.json()[i]["station"] == 11:
                            redOne = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 12:
                            redTwo = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 21:
                            blueOne = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 22:
                            blueTwo = personR.json()[i]["team_key"]
                    print(str(liveMatchKey) + " - Qual match " + str(currentMatch) + " ended")
                    queuingStr = ""
                    try:
                        if currentMatch + 1 < 10:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q00" + str(
                                currentMatch + 1) + "-1/participants", headers=apiHeaders)
                        else:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q0" + str(
                                currentMatch + 1) + "-1/participants", headers=apiHeaders)
                        redOneNext = ""
                        redTwoNext = ""
                        blueOneNext = ""
                        blueTwoNext = ""
                        for a in range(len(nextPersonR.json())):
                            if nextPersonR.json()[a]["station"] == 11:
                                redOneNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 12:
                                redTwoNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 21:
                                blueOneNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 22:
                                blueTwoNext = nextPersonR.json()[a]["team_key"]
                        queuingStr += "Next (" + str(currentMatch + 1) + ") = red [#" + str(redOneNext) + ", #" + str(
                            redTwoNext) + "], " + "blue [#" + str(blueOneNext) + ", #" + str(blueTwoNext) + "]; "
                        if currentMatch + 2 < 10:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q00" + str(
                                currentMatch + 2) + "-1/participants", headers=apiHeaders)
                        else:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKey) + "-Q0" + str(
                                currentMatch + 2) + "-1/participants", headers=apiHeaders)
                        redOneExtra = ""
                        redTwoExtra = ""
                        blueOneExtra = ""
                        blueTwoExtra = ""
                        for a in range(len(nextPersonR.json())):
                            if nextPersonR.json()[a]["station"] == 11:
                                redOneExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 12:
                                redTwoExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 21:
                                blueOneExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 22:
                                blueTwoExtra = nextPersonR.json()[a]["team_key"]
                        queuingStr += "2 matches away (" + str(currentMatch + 2) + ") = red [#" + str(
                            redOneExtra) + ", #" + str(redTwoExtra) + "], " + "blue [#" + str(
                            blueOneExtra) + ", #" + str(blueTwoExtra) + "]"
                    except KeyError:
                        print("KeyError")
                        continue
                    for i in liveScoreList:
                        metricCount(12)
                        if liveScorePredict[liveScoreList.index(i)] == 1 and r.json()[0]["red_score"] > r.json()[0][
                            "blue_score"]:
                            liveScoreScores[liveScoreList.index(i)] += 1
                            liveScorePredict[liveScoreList.index(i)] = 0
                        elif liveScorePredict[liveScoreList.index(i)] == 2 and r.json()[0]["red_score"] < r.json()[0][
                            "blue_score"]:
                            liveScoreScores[liveScoreList.index(i)] += 1
                            liveScorePredict[liveScoreList.index(i)] = 0
                        sendText(i, "Qual match " + str(currentMatch) + " has just ended! " + "Final score: " + str(
                            r.json()[0]["red_score"]) + " red [#" + str(redOne) + ", #" + str(redTwo) + "], " + str(
                            r.json()[0]["blue_score"]) + " blue [#" + str(blueOne) + ", #" + str(blueTwo) + "]")
                        sendText(i, queuingStr)
                    currentMatch += 1
        except KeyError:
            if not liveQualMode:
                break
        except TypeError:
            if not liveQualMode:
                break
    currentMatch = 1
    r = requests.get(apiURL + "match/" + str(liveMatchKey) + "-E001-1",
                     headers=apiHeaders)
    previousName = "NoPrev"
    while liveScoreRunning and str(previousName) != "Finals 3":
        time.sleep(5)
        if liveSkip:
            liveSkip = False
            currentMatch += 1
        try:
            if currentMatch < 10:
                r = requests.get(apiURL + "match/" + str(liveMatchKey) + "-E00" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKey) + "-E00" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            elif currentMatch < 100:
                r = requests.get(apiURL + "match/" + str(liveMatchKey) + "-E0" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKey) + "-E0" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            if r.json()[0]["red_score"] is not None and r.json()[0]["blue_score"] is not None:
                if r.json()[0]["red_score"] > 0 or r.json()[0]["blue_score"] > 0:
                    redOne = ""
                    redTwo = ""
                    blueOne = ""
                    blueTwo = ""
                    for i in range(len(personR.json())):
                        if personR.json()[i]["station"] < 19:
                            if personR.json()[i]["station_status"] != -1:
                                if redOne == "":
                                    redOne = personR.json()[i]["team_key"]
                                elif redTwo == "":
                                    redTwo = personR.json()[i]["team_key"]
                        if personR.json()[i]["station"] > 19:
                            if personR.json()[i]["station_status"] != -1:
                                if blueOne == "":
                                    blueOne = personR.json()[i]["team_key"]
                                elif blueTwo == "":
                                    blueTwo = personR.json()[i]["team_key"]
                    print(str(liveMatchKey) + " - Elim match " + str(currentMatch) + " ended")
                    previousName = str(r.json()[0]["match_name"])
                    for i in liveScoreList:
                        metricCount(12)
                        sendText(i, str(r.json()[0]["match_name"]) + " has just ended! " + "Final score: " + str(
                            r.json()[0]["red_score"]) + " red [#" + str(redOne) + ", #" + str(redTwo) + "], " + str(
                            r.json()[0]["blue_score"]) + " blue [#" + str(blueOne) + ", #" + str(blueTwo) + "]")
                        # Send score of prev match
                        # Get next 2 match competitors
                        # Get prev match competitors
                    currentMatch += 1
        except KeyError:
            continue
        except TypeError:
            continue
    liveMatchKey = ""
    liveScoreList = []
    liveScorePredict = []
    liveScoreScores = []
    liveScoreRunning = False


def checkLiveScoringTwo():  # live scoring channel 2
    global liveMatchKeyTwo
    global liveScoreListTwo
    global liveScoreRunningTwo
    global liveSkipTwo
    currentMatch = 1
    r = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q00" + str(currentMatch) + "-1",
                     headers=apiHeaders)
    while liveScoreRunningTwo:  # Keeps it running if no match schedule has been uploaded
        time.sleep(5)
        r = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q00" + str(currentMatch) + "-1",
                         headers=apiHeaders)
        print("Waiting for schedule")
        if "_code" not in r.json():
            break
    while liveScoreRunningTwo:
        time.sleep(2)
        if liveSkipTwo:
            liveSkipTwo = False
            currentMatch += 1
        try:
            if currentMatch < 10:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q00" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyTwo) + "-Q00" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            elif currentMatch < 100:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q0" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyTwo) + "-Q0" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            if r.json()[0]["red_score"] is not None and r.json()[0]["blue_score"] is not None:
                if r.json()[0]["red_score"] > 0 or r.json()[0]["blue_score"] > 0:
                    redOne = ""
                    redTwo = ""
                    blueOne = ""
                    blueTwo = ""
                    for i in range(len(personR.json())):
                        if personR.json()[i]["station"] == 11:
                            redOne = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 12:
                            redTwo = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 21:
                            blueOne = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 22:
                            blueTwo = personR.json()[i]["team_key"]
                    print(str(liveMatchKeyTwo) + " - Qual match " + str(currentMatch) + " ended")
                    queuingStr = ""
                    try:
                        if currentMatch + 1 < 10:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q00" + str(
                                currentMatch + 1) + "-1/participants", headers=apiHeaders)
                        else:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q0" + str(
                                currentMatch + 1) + "-1/participants", headers=apiHeaders)
                        redOneNext = ""
                        redTwoNext = ""
                        blueOneNext = ""
                        blueTwoNext = ""
                        for a in range(len(nextPersonR.json())):
                            if nextPersonR.json()[a]["station"] == 11:
                                redOneNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 12:
                                redTwoNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 21:
                                blueOneNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 22:
                                blueTwoNext = nextPersonR.json()[a]["team_key"]
                        queuingStr += "Next (" + str(currentMatch + 1) + ") = red [#" + str(redOneNext) + ", #" + str(
                            redTwoNext) + "], " + "blue [#" + str(blueOneNext) + ", #" + str(blueTwoNext) + "]; "
                        if currentMatch + 2 < 10:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q00" + str(
                                currentMatch + 2) + "-1/participants", headers=apiHeaders)
                        else:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-Q0" + str(
                                currentMatch + 2) + "-1/participants", headers=apiHeaders)
                        redOneExtra = ""
                        redTwoExtra = ""
                        blueOneExtra = ""
                        blueTwoExtra = ""
                        for a in range(len(nextPersonR.json())):
                            if nextPersonR.json()[a]["station"] == 11:
                                redOneExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 12:
                                redTwoExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 21:
                                blueOneExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 22:
                                blueTwoExtra = nextPersonR.json()[a]["team_key"]
                        queuingStr += "2 matches away (" + str(currentMatch + 2) + ") = red [#" + str(
                            redOneExtra) + ", #" + str(redTwoExtra) + "], " + "blue [#" + str(
                            blueOneExtra) + ", #" + str(blueTwoExtra) + "]"
                    except KeyError:
                        print("KeyError")
                        continue
                    for i in liveScoreListTwo:
                        metricCount(12)
                        sendText(i, "Qual match " + str(currentMatch) + " has just ended! " + "Final score: " + str(
                            r.json()[0]["red_score"]) + " red [#" + str(redOne) + ", #" + str(redTwo) + "], " + str(
                            r.json()[0]["blue_score"]) + " blue [#" + str(blueOne) + ", #" + str(blueTwo) + "]")
                        sendText(i, queuingStr)
                    currentMatch += 1
        except KeyError:
            if not liveQualModeTwo:
                break
        except TypeError:
            if not liveQualModeTwo:
                break
    currentMatch = 1
    r = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-E001-1",
                     headers=apiHeaders)
    previousName = "NoPrev"
    while liveScoreRunningTwo and str(previousName) != "Finals 3":
        time.sleep(5)
        if liveSkipTwo:
            liveSkipTwo = False
            currentMatch += 1
        try:
            if currentMatch < 10:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-E00" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyTwo) + "-E00" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            elif currentMatch < 100:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyTwo) + "-E0" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyTwo) + "-E0" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            if r.json()[0]["red_score"] is not None and r.json()[0]["blue_score"] is not None:
                if r.json()[0]["red_score"] > 0 or r.json()[0]["blue_score"] > 0:
                    redOne = ""
                    redTwo = ""
                    blueOne = ""
                    blueTwo = ""
                    for i in range(len(personR.json())):
                        if personR.json()[i]["station"] < 19:
                            if personR.json()[i]["station_status"] != -1:
                                if redOne == "":
                                    redOne = personR.json()[i]["team_key"]
                                elif redTwo == "":
                                    redTwo = personR.json()[i]["team_key"]
                        if personR.json()[i]["station"] > 19:
                            if personR.json()[i]["station_status"] != -1:
                                if blueOne == "":
                                    blueOne = personR.json()[i]["team_key"]
                                elif blueTwo == "":
                                    blueTwo = personR.json()[i]["team_key"]
                    print(str(liveMatchKeyTwo) + " - Elim match " + str(currentMatch) + " ended")
                    previousName = str(r.json()[0]["match_name"])
                    for i in liveScoreListTwo:
                        metricCount(12)
                        sendText(i, str(r.json()[0]["match_name"]) + " has just ended! " + "Final score: " + str(
                            r.json()[0]["red_score"]) + " red [#" + str(redOne) + ", #" + str(redTwo) + "], " + str(
                            r.json()[0]["blue_score"]) + " blue [#" + str(blueOne) + ", #" + str(blueTwo) + "]")
                        # Send score of prev match
                        # Get next 2 match competitors
                        # Get prev match competitors
                    currentMatch += 1
        except KeyError:
            continue
        except TypeError:
            continue
    liveMatchKeyTwo = ""
    liveScoreListTwo = []
    liveScoreRunningTwo = False


def checkLiveScoringThree():  # live scoring channel 3
    global liveMatchKeyThree
    global liveScoreListThree
    global liveScoreRunningThree
    global liveSkipThree
    currentMatch = 1
    r = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q00" + str(currentMatch) + "-1",
                     headers=apiHeaders)
    while liveScoreRunningThree:  # Keeps it running if no match schedule has been uploaded
        time.sleep(5)
        r = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q00" + str(currentMatch) + "-1",
                         headers=apiHeaders)
        print("Waiting for schedule")
        if "_code" not in r.json():
            break
    while liveScoreRunningThree:
        time.sleep(2)
        if liveSkipThree:
            liveSkipThree = False
            currentMatch += 1
        try:
            if currentMatch < 10:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q00" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyThree) + "-Q00" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            elif currentMatch < 100:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q0" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyThree) + "-Q0" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            if r.json()[0]["red_score"] is not None and r.json()[0]["blue_score"] is not None:
                if r.json()[0]["red_score"] > 0 or r.json()[0]["blue_score"] > 0:
                    redOne = ""
                    redTwo = ""
                    blueOne = ""
                    blueTwo = ""
                    for i in range(len(personR.json())):
                        if personR.json()[i]["station"] == 11:
                            redOne = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 12:
                            redTwo = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 21:
                            blueOne = personR.json()[i]["team_key"]
                        elif personR.json()[i]["station"] == 22:
                            blueTwo = personR.json()[i]["team_key"]
                    print(str(liveMatchKeyThree) + " - Qual match " + str(currentMatch) + " ended")
                    queuingStr = ""
                    try:
                        if currentMatch + 1 < 10:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q00" + str(
                                currentMatch + 1) + "-1/participants", headers=apiHeaders)
                        else:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q0" + str(
                                currentMatch + 1) + "-1/participants", headers=apiHeaders)
                        redOneNext = ""
                        redTwoNext = ""
                        blueOneNext = ""
                        blueTwoNext = ""
                        for a in range(len(nextPersonR.json())):
                            if nextPersonR.json()[a]["station"] == 11:
                                redOneNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 12:
                                redTwoNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 21:
                                blueOneNext = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 22:
                                blueTwoNext = nextPersonR.json()[a]["team_key"]
                        queuingStr += "Next (" + str(currentMatch + 1) + ") = red [#" + str(redOneNext) + ", #" + str(
                            redTwoNext) + "], " + "blue [#" + str(blueOneNext) + ", #" + str(blueTwoNext) + "]; "
                        if currentMatch + 2 < 10:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q00" + str(
                                currentMatch + 2) + "-1/participants", headers=apiHeaders)
                        else:
                            nextPersonR = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-Q0" + str(
                                currentMatch + 2) + "-1/participants", headers=apiHeaders)
                        redOneExtra = ""
                        redTwoExtra = ""
                        blueOneExtra = ""
                        blueTwoExtra = ""
                        for a in range(len(nextPersonR.json())):
                            if nextPersonR.json()[a]["station"] == 11:
                                redOneExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 12:
                                redTwoExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 21:
                                blueOneExtra = nextPersonR.json()[a]["team_key"]
                            elif nextPersonR.json()[a]["station"] == 22:
                                blueTwoExtra = nextPersonR.json()[a]["team_key"]
                        queuingStr += "2 matches away (" + str(currentMatch + 2) + ") = red [#" + str(
                            redOneExtra) + ", #" + str(redTwoExtra) + "], " + "blue [#" + str(
                            blueOneExtra) + ", #" + str(blueTwoExtra) + "]"
                    except KeyError:
                        print("KeyError")
                        continue
                    for i in liveScoreListThree:
                        metricCount(12)
                        sendText(i, "Qual match " + str(currentMatch) + " has just ended! " + "Final score: " + str(
                            r.json()[0]["red_score"]) + " red [#" + str(redOne) + ", #" + str(redTwo) + "], " + str(
                            r.json()[0]["blue_score"]) + " blue [#" + str(blueOne) + ", #" + str(blueTwo) + "]")
                        sendText(i, queuingStr)
                    currentMatch += 1
        except KeyError:
            if not liveQualModeThree:
                break
        except TypeError:
            if not liveQualModeThree:
                break
    currentMatch = 1
    r = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-E001-1",
                     headers=apiHeaders)
    previousName = "NoPrev"
    while liveScoreRunningThree and str(previousName) != "Finals 3":
        if liveSkipThree:
            liveSkipThree = False
            currentMatch += 1
        time.sleep(5)
        try:
            if currentMatch < 10:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-E00" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyThree) + "-E00" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            elif currentMatch < 100:
                r = requests.get(apiURL + "match/" + str(liveMatchKeyThree) + "-E0" + str(currentMatch) + "-1",
                                 headers=apiHeaders)
                personR = requests.get(
                    apiURL + "match/" + str(liveMatchKeyThree) + "-E0" + str(currentMatch) + "-1/participants",
                    headers=apiHeaders)
            if r.json()[0]["red_score"] is not None and r.json()[0]["blue_score"] is not None:
                if r.json()[0]["red_score"] > 0 or r.json()[0]["blue_score"] > 0:
                    redOne = ""
                    redTwo = ""
                    blueOne = ""
                    blueTwo = ""
                    for i in range(len(personR.json())):
                        if personR.json()[i]["station"] < 19:
                            if personR.json()[i]["station_status"] != -1:
                                if redOne == "":
                                    redOne = personR.json()[i]["team_key"]
                                elif redTwo == "":
                                    redTwo = personR.json()[i]["team_key"]
                        if personR.json()[i]["station"] > 19:
                            if personR.json()[i]["station_status"] != -1:
                                if blueOne == "":
                                    blueOne = personR.json()[i]["team_key"]
                                elif blueTwo == "":
                                    blueTwo = personR.json()[i]["team_key"]
                    print(str(liveMatchKeyThree) + " - Elim match " + str(currentMatch) + " ended")
                    previousName = str(r.json()[0]["match_name"])
                    for i in liveScoreListThree:
                        metricCount(12)
                        sendText(i, str(r.json()[0]["match_name"]) + " has just ended! " + "Final score: " + str(
                            r.json()[0]["red_score"]) + " red [#" + str(redOne) + ", #" + str(redTwo) + "], " + str(
                            r.json()[0]["blue_score"]) + " blue [#" + str(blueOne) + ", #" + str(blueTwo) + "]")
                        # Send score of prev match
                        # Get next 2 match competitors
                        # Get prev match competitors
                    currentMatch += 1
        except KeyError:
            continue
        except TypeError:
            continue
    liveMatchKeyThree = ""
    liveScoreListThree = []
    liveScoreRunningThree = False

def checkLiveScoringFTCScores():  # live scoring channel 3
    global FTCScoresRunning
    global FTCScoresMatchKey
    global FTCScoresList
    global liveSkipThree
    currentMatch = 0
    FTCScoresRunning = True
    FTCScoresApi = "https://api.ftcscores.com/api/"
    while FTCScoresRunning:
        time.sleep(2)
        r = requests.get(FTCScoresApi + "events/" + str(FTCScoresMatchKey))
        if str(r.json()["matches"][currentMatch]["status"]) == "done":
            redOne = str(r.json()["matches"][currentMatch]["teams"]["red"][0]["number"])
            redTwo = str(r.json()["matches"][currentMatch]["teams"]["red"][1]["number"])
            blueOne = str(r.json()["matches"][currentMatch]["teams"]["blue"][0]["number"])
            blueTwo = str(r.json()["matches"][currentMatch]["teams"]["blue"][1]["number"])
            print(str(liveMatchKeyThree) + " - Qual match " + str(currentMatch+1) + " ended")
            queuingStr = ""
            try:
                redOneNext = str(r.json()["matches"][currentMatch+1]["teams"]["red"][0]["number"])
                redTwoNext = str(r.json()["matches"][currentMatch+1]["teams"]["red"][1]["number"])
                blueOneNext = str(r.json()["matches"][currentMatch+1]["teams"]["blue"][0]["number"])
                blueTwoNext = str(r.json()["matches"][currentMatch+1]["teams"]["blue"][1]["number"])
                queuingStr += "Next (" + str(currentMatch + 2) + ") = red [#" + str(redOneNext) + ", #" + str(
                    redTwoNext) + "], " + "blue [#" + str(blueOneNext) + ", #" + str(blueTwoNext) + "]; "
                redOneExtra = str(r.json()["matches"][currentMatch + 2]["teams"]["red"][0]["number"])
                redTwoExtra = str(r.json()["matches"][currentMatch + 2]["teams"]["red"][1]["number"])
                blueOneExtra = str(r.json()["matches"][currentMatch + 2]["teams"]["blue"][0]["number"])
                blueTwoExtra = str(r.json()["matches"][currentMatch + 2]["teams"]["blue"][1]["number"])
                queuingStr += "2 matches away (" + str(currentMatch + 3) + ") = red [#" + str(
                    redOneExtra) + ", #" + str(redTwoExtra) + "], " + "blue [#" + str(
                    blueOneExtra) + ", #" + str(blueTwoExtra) + "]"
            except KeyError:
                print("KeyError")
                continue
            for i in FTCScoresList:
                metricCount(12)
                sendText(i, "Qual match " + str(currentMatch+1) + " has just ended! " + "Final score: " + str(
                    r.json()["matches"][currentMatch]["scores"]["red"]) + " red [#" + str(redOne) + ", #" + str(redTwo) + "], " + str(
                    r.json()["matches"][currentMatch]["scores"]["blue"]) + " blue [#" + str(blueOne) + ", #" + str(blueTwo) + "]")
                time.sleep(0.5)
                sendText(i, queuingStr)
            currentMatch += 1
    FTCScoresMatchKey = ""
    FTCScoresList = []
    FTCScoresRunning = False


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
    global liveScoreRunning
    global liveMatchKey
    global liveScoreList
    global liveScoreScores
    global liveScorePredict
    global liveSkip
    global liveQualMode
    global liveScoreRunningTwo
    global liveMatchKeyTwo
    global liveScoreListTwo
    global liveSkipTwo
    global liveMatchKeyThree
    global liveScoreListThree
    global liveScoreRunningThree
    global liveSkipThree
    global FTCScoresList
    global FTCScoresMatchKey
    global FTCScoresRunning
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
        elif "metrics" in msg or "metrix" in msg:
            print("Admin " + str(number) + " used the metrics command")
            sendText(number, metricGet())
            return True
        elif "metrics2" in msg or "metrix2" in msg:
            print("Admin " + str(number) + " used the metrics command")
            sendText(number, metricTwoGet())
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
                if "2019-02-02" in eventsList[i]["start_date"]:
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
        if "togglelive" in msg:
            try:
                if "1819" in msg[msg.index("togglelive") + 1]:
                    print("Admin " + str(number) + " used the toggleLive command")
                    if liveScoreRunning:
                        sendText(number, "You have manually ended live scoring alert thread 1")
                        liveMatchKey = ""
                        liveScoreList = []
                        liveScorePredict = []
                        liveScoreScores = []
                        liveScoreRunning = False
                    elif not liveScoreRunning:
                        liveScoreRunning = True
                        sendText(number, "You have started live scoring alert thread")
                        liveMatchKey = str(msg[msg.index("togglelive") + 1])
                        liveScoreList.append(str(number))
                        liveScorePredict.append(int(0))
                        liveScoreScores.append(int(0))
                        liveThread = liveScoringThread("LiveThread", str(number))
                        liveThread.start()
                    return True
                else:
                    sendText(number, "ToggleLive missing match key [toggleLive:(matchKey)]")
                    return True
            except IndexError:
                sendText(number, "ToggleLive missing match key [toggleLive:(matchKey)]")
                return True
        elif "togglelive2" in msg:
            if "1819" in msg[msg.index("togglelive2") + 1]:
                print("Admin " + str(number) + " used the toggleLive2 command")
                if liveScoreRunningTwo:
                    sendText(number, "You have manually ended live scoring alert thread 2")
                    liveMatchKeyTwo = ""
                    liveScoreListTwo = []
                    liveScoreRunningTwo = False
                elif not liveScoreRunningTwo:
                    liveScoreRunningTwo = True
                    sendText(number, "You have started live scoring alert thread 2")
                    liveMatchKeyTwo = str(msg[msg.index("togglelive2") + 1])
                    liveScoreListTwo.append(str(number))
                    liveThreadTwo = liveScoringThreadTwo("LiveThread2", str(number))
                    liveThreadTwo.start()
                return True
            else:
                sendText(number, "ToggleLive missing match key [toggleLive:(matchKey)]")
                return True
        elif "togglelive3" in msg:
            if "1819" in msg[msg.index("togglelive3") + 1]:
                print("Admin " + str(number) + " used the toggleLive3 command")
                if liveScoreRunningThree:
                    sendText(number, "You have manually ended live scoring alert thread 3")
                    liveMatchKeyThree = ""
                    liveScoreListThree = []
                    liveScoreRunningThree = False
                elif not liveScoreRunningThree:
                    liveScoreRunningThree = True
                    sendText(number, "You have started live scoring alert thread 3")
                    liveMatchKeyThree = str(msg[msg.index("togglelive3") + 1])
                    liveScoreListThree.append(str(number))
                    liveThreadThree = liveScoringThreadThree("LiveThread3", str(number))
                    liveThreadThree.start()
                return True
            else:
                sendText(number, "ToggleLive missing match key [toggleLive:(matchKey)]")
                return True
        elif "toggleftcscores" in msg:
            print("Admin " + str(number) + " used the toggleLive3 command")
            msg = rawRequest.split(" ")
            if FTCScoresRunning:
                sendText(number, "You have manually ended live scoring alert thread 3")
                FTCScoresMatchKey = ""
                FTCScoresList = []
                FTCScoresRunning = False
            elif not FTCScoresRunning:
                FTCScoresRunning = True
                sendText(number, "You have started live scoring alert FTCScores")
                FTCScoresMatchKey = str(msg[msg.index("toggleftcscores") + 1])
                FTCScoresList.append(str(number))
                FTCScoresThreadA = FTCScoresThread("LiveThreadFTCScores", str(number))
                FTCScoresThreadA.start()
            return True
        elif "skiplive" in msg:
            liveSkip = True
            print("Admin " + str(number) + " used the skipLive command")
            sendText(number, "Attempted to skip match")
            return True
        elif "skiplive2" in msg:
            liveSkipTwo = True
            print("Admin " + str(number) + " used the skipLiveTwo command")
            sendText(number, "Attempted to skip match")
            return True
        elif "skiplive3" in msg:
            liveSkipThree = True
            print("Admin " + str(number) + " used the skipLiveThree command")
            sendText(number, "Attempted to skip match")
            return True
        elif "livequalmode" in msg:
            if liveQualMode:
                liveQualMode = False
                sendText(number, "Holding in qualification matches has been disabled")
            elif not liveQualMode:
                liveQualMode = True
                sendText(number, "Holding in qualification mode is now enabled")
            return True
    else:
        return False


def metricCount(action):  # Code to log metrics
    with open("metric.json", "r") as read_file:
        data = json.load(read_file)
    metricList = ["textsRec", "locGet", "nameGet", "yearGet", "webGet", "eveGet", "awardGet", "helpGet", "avgTotalGet","avgGet",
                  "matchGet", "livesSent"]
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
    metricStr += "Live Alerts sent - " + str(data["livesSent"])
    return metricStr


def loadAdminList():  # Loads admin numbers off admin.json
    global adminList
    global eventAdminList
    adminList = []
    eventAdminList = []
    with open("admin.json", "r") as read_file:
        data = json.load(read_file)
    for i in range(len(data["fileAdminList"])):
        adminList.append(str(data["fileAdminList"][i]["admin_num"]))
        eventAdminList.append(str(data["fileAdminList"][i]["admin_num"]))
    for i in range(len(data["fileEventAdminList"])):
        eventAdminList.append(str(data["fileEventAdminList"][i]["admin_num"]))
    print(str(adminList))


def loadTwilio():  # Loads Twilio account info off twilio.json
    global twilioAuth
    global twilioAccountID
    global apiHeaders
    with open("twilio.json", "r") as read_file:
        data = json.load(read_file)
    twilioAuth = str(data["twilioAuth"])
    twilioAccountID = str(data["twilioID"])
    apiHeaders = {'content-type': 'application/json',
                  'X-TOA-KEY': str(data["toaKey"]),
                  'X-Application-Origin': 'TOAText'}


def loadAllTeams():  # Requests list of all teams to be stored for string matching
    global allTeams
    print("All teams requested")
    teamsR = requests.get(apiURL + "team/",
                          headers=apiHeaders)
    allTeams = teamsR.json()
    print("Recieved all teams")

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
        sendText(number, "You have now opted out of ALL TOAText messages. Send START to rejoin")
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
    loadTwilio()
    loadAllTeams()
    checkAdminMsg(str(adminList[0]), ["updateavg", "startup"], "")  # Does a update for the averages upon boot
    sendText(str(adminList[0]), "TOAText finished bootup sequence")
    pingList.append(str(adminList[0]))
    app.run(host='0.0.0.0', port=5001)