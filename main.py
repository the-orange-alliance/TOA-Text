import requests
from twilio import twiml
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import boto3
from botocore.exceptions import ClientError
import random as rand
import threading
import json
import email
import email.utils
from time import sleep
from flask import Flask, request, make_response
from fuzzywuzzy import fuzz
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

SENDER = "The Orange Alliance <toa@notifications.maths22.com>"
AWS_REGION = "us-west-2"
CHARSET = "UTF-8"

cred = credentials.Certificate('TOAFirebase.json')
default_app = firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://the-orange-alliance.firebaseio.com/'
})
'''
Places to edit for Detroit:
Join alerts commands
Admin stats command
Help
Schedule
Streams
'''
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
sesAccessKeyId = ''
sesSecretAccessKey = ''

# global val for average comp last weekend
autoSum = 0
teleOpSum = 0

rateLimit = 2

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

class newAlert(threading.Thread):  # Thread created upon request
    def __init__(self, name, parsedJson):
        threading.Thread.__init__(self)
        self.name = name
        self.parsedJson = parsedJson
    def run(self):
        print("Starting live alert for " + self.name)
        liveAlerts(self.parsedJson)
        print("Finished live alert for " + self.name)

class sendText(threading.Thread):  # Thread created upon request
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
    def run(self):
        print("Started queue manager")
        while True:
            queueManage()

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

@app.route("/email", methods=['POST'])
def receiveEmail():  # Code executed upon receiving text
    type = request.headers['x-amz-sns-message-type']
    if type == 'SubscriptionConfirmation':
        url = json.loads(request.data)['SubscribeURL']
        requests.get(url)
        return ("OK")
    elif type == 'Notification':
        payload = json.loads(request.data)['Message']
        # app.logger.info('Payload: ' + str(payload))
        parsed = json.loads(payload)
        #get just the email address
        email_address = email.utils.parseaddr(parsed['mail']['commonHeaders']['from'][0])[1].replace('.',',')
        b = email.message_from_string(parsed['content'])
        message_body = ""
        if b.is_multipart():
            for part in b.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))

                # skip any text/plain (txt) attachments
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    message_body = part.get_payload(decode=True)  # decode
                    break
        # not multipart - i.e. plain text, no attachments, keeping fingers crossed
        else:
            message_body = b.get_payload(decode=True)
        # print("Received from: " + str(number))
        message_body = message_body.strip()
        t = incomingText(email_address, email_address, message_body)
        t.start()
        return ("ok")

@app.route("/receiveHook", methods=['POST'])
def newLiveAlerts(): #Captures generic match info
    if webhookKey == request.headers.get('webhookKey') or request.environ['REMOTE_ADDR'] == "127.0.0.1":
        matchInfo = request.get_json(force=True)
        if matchInfo['message_type'] != "match_scored":
            return 'wrong_type'
        t = newAlert(matchInfo['message_data']['match_key'], matchInfo)
        t.start()
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

def trimNumber(number):
    if "@" in number:
        return number
    else:
        return number[1:]

def processText(number, msg, override = False):  # Code to send outgoing text
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    userNum = trimNumber(number)
    if not phoneDB[userNum]['opted'] and not override:
        return
    with open("queue.json", "r") as read_file:
        data = json.load(read_file)
    msgDict = {"msg":  str(msg), "number": str(number)}
    data["queue"].append(msgDict)
    with open("queue.json", "w") as write_file:
        json.dump(data, write_file)

def queueManage():
    sleep(0.2)
    account_sid = twilioAccountID
    auth_token = twilioAuth
    client = Client(account_sid, auth_token)

    aws_client = boto3.client('ses',
        region_name=AWS_REGION,
        aws_access_key_id=sesAccessKeyId,
        aws_secret_access_key=sesSecretAccessKey
    )

    with open("queue.json", "r") as read_file:
        data = json.load(read_file)
    queued = 0
    for sms in client.messages.list(limit=50):
        if sms.status == "queued":
            queued += 1
    if len(data["queue"]) < 1:
        return
    elif queued >= rateLimit or disableMode == 1:
        return
    else:
        msg = data["queue"][0]["msg"]
        number = data["queue"][0]["number"]
        data["queue"].pop(0)
    with open("queue.json", "w") as write_file:
        json.dump(data, write_file)
    if "@" in number:
        try:
            response = aws_client.send_email(
                Destination={
                    'ToAddresses': [ str(number.replace(',', '.')) ],
                },
                Message={
                    'Body': {
                        'Text': {
                            'Charset': CHARSET,
                            'Data': str(msg),
                        },
                    },
                    'Subject': {
                        'Charset': CHARSET,
                        'Data': '',
                    },
                },
                Source=SENDER,
            )
        # Display an error if something goes wrong.	
        except ClientError as e:
            app.logger.error(e.response['Error']['Message'])
    elif "+1" in number and number in numTwoList:
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

def liveAlerts(matchInfo):
    refDB = db.reference('liveEvents')
    eventsDB = refDB.order_by_key().get()
    redList = []
    blueList = []
    personR = requests.get(apiURL + "match/" + matchInfo['message_data']['match_key'] + "/participants",
                           headers=apiHeaders)
    for i in range(len(personR.json())):
        if personR.json()[i]["station"] < 19:
            redList.append(int(personR.json()[i]["team_key"]))
        elif personR.json()[i]["station"] > 19:
            blueList.append(int(personR.json()[i]["team_key"]))
    userMsg = ""
    #Check if score update
    with open("sentKeys.json", "r") as read_file:
        data = json.load(read_file)
    if matchInfo['message_data']['match_key'] in data["keys"]:
        userMsg += "[Score Update] "
    else:
        data["keys"].append(matchInfo['message_data']['match_key'])
    with open("sentKeys.json", "w") as write_file:
        json.dump(data, write_file)
    #Find event name
    if "DET2" in matchInfo['message_data']['match_key']:
        userMsg += "Ochoa - "
    elif "DET1" in matchInfo['message_data']['match_key']:
        userMsg += "Edison - "
    elif "DET0" in matchInfo['message_data']['match_key']:
        userMsg += "Detroit Finals - "
    elif "TEST" in matchInfo['message_data']['match_key']:
        userMsg += "Test - "
    if int(matchInfo['message_data']["red_score"]) > int(matchInfo['message_data']["blue_score"]):
        userMsg += str(matchInfo['message_data']["match_name"]) + " went to the red alliance! "
    elif int(matchInfo['message_data']["red_score"]) < int(matchInfo['message_data']["blue_score"]):
        userMsg += str(matchInfo['message_data']["match_name"]) + " went to the blue alliance! "
    elif int(matchInfo['message_data']["red_score"]) == int(matchInfo['message_data']["blue_score"]):
        userMsg += str(matchInfo['message_data']["match_name"]) + " was a tie! "
    else:
        userMsg += str(matchInfo['message_data']["match_name"]) + " just ended! "
    userMsg += str(matchInfo['message_data']["red_score"]) + " red " + str(redList) + ", "
    userMsg += str(matchInfo['message_data']["blue_score"]) + " blue " + str(blueList) + " "
    if disableMode == 0:
        for userNum in eventsDB[matchInfo['message_data']["event_key"]]:
            savedInfo = eventsDB[matchInfo['message_data']["event_key"]][userNum]
            if savedInfo['global'] and len(savedInfo) == 1:
                processText("+" + userNum, userMsg)
            elif savedInfo['global']:
                for teams in savedInfo.keys():
                    if teams == 'global':
                        continue
                    try:
                        if int(teams) in redList or int(teams) in blueList:
                            processText("+" + userNum, "[Team " + str(teams) + " Alert] " + userMsg)
                            break
                    except:
                        break
                else:
                    processText("+" + userNum, userMsg)
            elif not savedInfo['global'] and len(savedInfo) > 1:
                for teams in savedInfo.keys():
                    if teams == 'global':
                        continue
                    if teams in redList or teams in blueList:
                        processText("+" + userNum, "[Team " + str(teams) + " Alert] " + userMsg)
                        break
    return

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
    "updateavg": "updates average score to previous weekends",
    "ratelim": "sets the maximum number of texts allowed in the twilio queue",
    "queueinfo": "returns the number of texts in the queue and the current limit out of 50",
    "clearqueue": "clears ALL queued messages"
}
event_command_descriptions = {
    "togglelive": "toggles the state of live scoring [togglelive:[matchKey]]",
    "liveskip": "Skips over live match if a single match is missing from DataSync",
    "livequalmode": "Prevents advancement from quals if toggled"
}


def respond_by_command(descriptions, splitParts, number):
    for command, description in descriptions.items():
        if command in splitParts:
            processText(number, command + " - " + description)
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
            processText(number,
                     "Begin text with team number and then spaces or : to separate commands. Send a team number with nothing else to be provided a brief overview")
            processText(number,
                     "Detroit Worlds special commands - addEdison + addOchoa (to join live alerts!), streams, schedule")
            processText(number,
                     "Available team requests are: location, name, startYear, website, events, awards, avgScore, matchinfo, livestats, OPR")
            processText(number,
                     "Available non-team requests are: avgTotalScore, about, flip, searchTN. Example - 15692:location:name:events or 15692 shortname awards")
            adminHelpStr = ""
            if number in adminList:
                adminHelpStr += "Admin requests: currentInfo, freeze, metrics, pingme, updateavg, updateAdmins, serverstatus, ratelim, queueinfo, clearqueue"
            if number in eventAdminList:
                processText(number, adminHelpStr)
            processText(number,
                     "Use ?:[command] to know more! Text STOP to opt-out of using TOAText. Use START to opt back into TOAText.")
            processText(number,
                        "Text MSGOPT to toggle getting TOA Annoucements through TOAText")
        return True
    elif "about" in splitParts:
        processText(number,
                 "TOAText is a portable, on-the-go version of The Orange Alliance. It can provide information about teams, along with statistics")
        processText(number, "Created by Team 15692 in collaboration with The Orange Alliance. Special thanks to Dominic Hupp for maintaining this project")
        processText(number, "To know more about any commands, use ?:[command] or help:[command]")
        return True
    elif "newcmds" in splitParts:
        processText(number, "New features - checklives, livestats, matchinfo, addLive, searchTN, OPR")
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
        processText(number, pickupList[randomNum])
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
        processText(number, str(runningKeys))
        return True'''

def champsCmds(number, splitParts):
    if "streams" in splitParts or "stream" in splitParts:
        textStr = "Streams: \n"
        textStr += "Edison - https://twitch.tv/firstinspires_edison \n"
        textStr += "Ochoa - https://twitch.tv/firstinspires_ochoa"
        processText(number, textStr)
        processText(number, "First Championship Channel - https://player.twitch.tv/?channel=firstinspires")
        return True
    elif "schedule" in splitParts:
        textStr = "Schedule: \n"
        textStr += "Edison - http://toa.events/1819-CMP-DET1 \n"
        textStr += "Ochoa - http://toa.events/1819-CMP-DET2"
        processText(number, textStr)
        return True
    return False

def avgPoints(number, splitParts):  # Average total points
    if "avgtotalscore" in splitParts or "avgtotalpoints" in splitParts:
        print(number + " requested average score")
        processText(number, "Average auto score - " + str(round(autoSum, 2)) + " || Average TeleOp score - " + str(
            round(teleOpSum, 2)) + " || Average score - " + str(round(float(autoSum + teleOpSum), 2)))
        return True

def addLive(number, splitParts):  # Adds users to live alert threads Edison or Ochoa
    '''if "addlive" in splitParts and liveMatchKey != "":
        print(str(number) + " Used AddLive")
        refDB = db.reference('liveEvents/' + str(liveMatchKey).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if trimNumber(number) in eventDB:
            refDB.update({str(trimNumber(number)): None})
            processText(number, "You have been removed from the live scoring alerts")
        elif trimNumber(number) not in eventDB:
            try:
                refDB.update({str(trimNumber(number)): True})
            except AttributeError:
                refDB.set({str(trimNumber(number)): True})
            processText(number, "You have been added to the live scoring alerts. Send addLive again to be removed")
            processText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive" in splitParts:
        processText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addlive2" in splitParts and liveMatchKeyTwo != "":
        print(str(number) + " Used AddLive2")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyTwo).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if trimNumber(number) in eventDB:
            refDB.update({str(trimNumber(number)): None})
            processText(number, "You have been removed from the live scoring alerts")
        elif trimNumber(number) not in eventDB:
            try:
                refDB.update({str(trimNumber(number)): True})
            except AttributeError:
                refDB.set({str(trimNumber(number)): True})
            processText(number, "You have been added to the live scoring alerts. Send addLive2 again to be removed")
            processText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive2" in splitParts:
        processText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addliveftcscores" in splitParts:
        print(str(number) + " Used addliveftcscores")
        if number in FTCScoresList:
            FTCScoresList.remove(number)
            processText(number, "You have been removed from the live scoring alerts")
        elif number not in FTCScoresList:
            FTCScoresList.append(number)
            processText(number, "You have been added to the live scoring alerts. Send addliveftcscores again to be removed")
            processText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    if "addlive3" in splitParts and liveMatchKeyThree != "":
        print(str(number) + " Used AddLive3")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyThree).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if trimNumber(number) in eventDB:
            refDB.update({str(trimNumber(number)): None})
            processText(number, "You have been removed from the live scoring alerts")
        elif trimNumber(number) not in eventDB:
            try:
                refDB.update({str(trimNumber(number)): True})
            except AttributeError:
                refDB.set({str(trimNumber(number)): True})
            processText(number, "You have been added to the live scoring alerts. Send addLive3 again to be removed")
            processText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive3" in splitParts:
        processText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addlive4" in splitParts and liveMatchKeyFour != "":
        print(str(number) + " Used AddLive4")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyFour).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if trimNumber(number) in eventDB:
            refDB.update({str(trimNumber(number)): None})
            processText(number, "You have been removed from the live scoring alerts")
        elif trimNumber(number) not in eventDB:
            try:
                refDB.update({str(trimNumber(number)): True})
            except AttributeError:
                refDB.set({str(trimNumber(number)): True})
            processText(number, "You have been added to the live scoring alerts. Send addLive4 again to be removed")
            processText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive4" in splitParts:
        processText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True
    if "addlive5" in splitParts and liveMatchKeyFive != "":
        print(str(number) + " Used AddLive4")
        refDB = db.reference('liveEvents/' + str(liveMatchKeyFive).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
        except AttributeError:
            eventDB = []
        if trimNumber(number) in eventDB:
            refDB.update({str(trimNumber(number)): None})
            processText(number, "You have been removed from the live scoring alerts")
        elif trimNumber(number) not in eventDB:
            try:
                refDB.update({str(trimNumber(number)): True})
            except AttributeError:
                refDB.set({str(trimNumber(number)): True})
            processText(number, "You have been added to the live scoring alerts. Send addLive5 again to be removed")
            processText(number,
                     "The Orange Alliance and Team 15692 (and their members) are NOT responsible for any missed matches. Please be responsible")
        return True
    elif "addlive5" in splitParts:
        processText(number, "That channel is not currently live. Try again later or subscribe from the web portal!")
        return True'''
    if "add" in splitParts and "edison" in splitParts or "addedison" in splitParts:
        edisonKey = "1819-CMP-DET1"
        refDB = db.reference('liveEvents/' + str(edisonKey).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
            numDB = refDB.order_by_key().get()
        except AttributeError:
            eventDB = []
        foundTN = ""
        for split in splitParts:
            if split.isdigit():
                foundTN = str(split)
                break
        if foundTN == "":
            if trimNumber(number) in eventDB and numDB[trimNumber(number)]['global']:
                refDB.child(trimNumber(number)).update({'global': False})
                processText(number, "You have been removed from the live scoring alerts")
            elif trimNumber(number) not in eventDB or not numDB[trimNumber(number)]['global']:
                try:
                    refDB.child(trimNumber(number)).update({'global': True})
                except AttributeError:
                    refDB.child(trimNumber(number)).set({'global': True})
                processText(number, "You have been added to the live scoring alerts for Detroit Worlds - Edison Division. Send 'Add Edison' again to be removed")
                processText(number, "The Orange Alliance is NOT responsible for any missed matches. Please be responsible and best of luck!")
        else:
            try:
                if str(foundTN) in numDB[str(trimNumber(number))]:
                    pass
            except:
                refDB.child(trimNumber(number)).set({'global': False})
                refDB = db.reference('liveEvents/' + str(edisonKey).upper())
                numDB = refDB.order_by_key().get()
            if foundTN in numDB[str(trimNumber(number))].keys():
                refDB.child(trimNumber(number)).update({str(foundTN): None})
                processText(number, "You have been removed from the live scoring alerts for team " + foundTN)
            else:
                try:
                    refDB.child(trimNumber(number)).update({str(foundTN): True})
                except:
                    refDB.child(trimNumber(number)).set({str(foundTN): True, 'global': False})
                processText(number, "You have been added to live alerts for Detroit Worlds - Edison Division team " + foundTN + ". Send 'Add Edison " + foundTN + "' again to be removed")
        return True
    if "add" in splitParts and "ochoa" in splitParts or "addochoa" in splitParts:
        ochoaKey = "1819-CMP-DET2"
        refDB = db.reference('liveEvents/' + str(ochoaKey).upper())
        try:
            eventDB = list(refDB.order_by_key().get().keys())
            numDB = refDB.order_by_key().get()
        except AttributeError:
            eventDB = []
        foundTN = ""
        for split in splitParts:
            if split.isdigit():
                foundTN = str(split)
                break
        if foundTN == "":
            if trimNumber(number) in eventDB and numDB[trimNumber(number)]['global']:
                refDB.child(trimNumber(number)).update({'global': False})
                processText(number, "You have been removed from the live scoring alerts")
            elif trimNumber(number) not in eventDB or not numDB[trimNumber(number)]['global']:
                try:
                    refDB.child(trimNumber(number)).update({'global': True})
                except AttributeError:
                    refDB.child(trimNumber(number)).set({'global': True})
                processText(number, "You have been added to the live scoring alerts for Detroit Worlds - Ochoa Division. Send 'Add Ochoa' again to be removed")
                processText(number, "The Orange Alliance is NOT responsible for any missed matches. Please be responsible and best of luck!")
        else:
            try:
                if str(foundTN) in numDB[str(trimNumber(number))]:
                    pass
            except:
                refDB.child(trimNumber(number)).set({'global': False})
                refDB = db.reference('liveEvents/' + str(ochoaKey).upper())
                numDB = refDB.order_by_key().get()
            if foundTN in numDB[str(trimNumber(number))].keys():
                refDB.child(trimNumber(number)).update({str(foundTN): None})
                processText(number, "You have been removed from the live scoring alerts for team " + foundTN)
            else:
                try:
                    refDB.child(trimNumber(number)).update({str(foundTN): True})
                except:
                    refDB.child(trimNumber(number)).set({str(foundTN): True, 'global': False})
                processText(number, "You have been added to live alerts for Detroit Worlds - Ochoa Division team " + foundTN + ". Send 'Add Ochoa " + foundTN + "' again to be removed")
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
    processText(number, errorMsgText)

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
                processText(number, "That team name was not found. Please try again")
            elif found == True:
                if ":" in raw:
                    searchingName = str(raw.split(":", 2)[2])
                else:
                    searchingName = str(raw.split(" ", 2)[2])
                processText(number, str(searchingName) + " could be team " + str(possible[:-2]))
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
                processText(number, "That is an invalid search word. (EC3 - Overflow)")
                return True
            if found == False:
                processText(number, "That team name was not found. Please try again")
            elif found == True:
                if ":" in raw:
                    searchingName = str(raw.split(":", 1)[1])
                else:
                    searchingName = str(raw.split(" ", 1)[1])
                processText(number, formatResp(str(searchingName) + " could be team " + str(possible), "", 0))
        else:
            processText(number, "That is not a valid team name")
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
            processText(number, "All admin in help list have been pinged")
            splitParts = rawRequest.lower().replace(" ", " ").split(":")
            for i in helpNumList:
                processText(i, "Help requested from " + str(number))
                processText(i, "From user: " + splitParts[splitParts.index("sendhelp") + 1])
        elif number in bannedNums:
            processText(number,
                     "You have been banned from using sendHelp. Ping @Huppdo on discord in the FTC or TOA discord servers to discuss")
        else:
            processText(number,
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
                            processText(number, "Team " + str(splitParts[splitParts.index("team") + 1]) + " is ranked " + str(rankR.json()[i]["rank"]) + " at their current event.")
                            break
                except:
                    processText(number, "Sorry, however that information could not be found. Perhaps the rankings for this event aren't uploaded yet")
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
                processText(number, "Please provide a more indepth command for livestats")
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
                processText(number,
                         "Top ranked team - " + str(topTeam) + ", 2nd - " + str(secTeam) + ", 3rd - " + str(thirdTeam))
            except:
                processText(number,
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
                processText(adminNum, number + " made a request")
    if sendMass(splitParts, msg, number):
        return
    if checkAdminMsg(number, splitParts, msg) is True:  # Check if admin request was made
        return
    if checkHelp(splitParts, number) is True:  # Checks if a help request was made
        metricCount(8)
        return
    if playGames(number, splitParts) is True:
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
        processText(number,
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
                    processText(number,"The OPR for " + str(splitParts[splitParts.index("team") + 1]) + " at " + namer.json()[0]["event_name"] + " (" + namer.json()[0]["start_date"][:10]  + ") was " + str(eventr.json()[a]["opr"]))
                    msgSent = True
                    break
        if not msgSent:
            processText(number, "This team did not have any OPRs tied to it. Check again later")
        return True

def checkOnlyTeam(teamNum, number):  # Code for if request just has team
    r = requests.get(apiURL + "team/" + teamNum, headers=apiHeaders)
    splitParts = ['team', 'location', 'shortname', 'startyear', 'events']
    splitParts.insert(1, teamNum)
    if "_code" not in r.json():
        refDB = db.reference('Phones')
        userNum = trimNumber(number)
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
            processText(number, formatResp(basicInfo, advancedInfo, 1))
    else:
        processText(number, "Invalid Team Number")
        return False

def playGames(number, splitParts):  # plays flip a coin or RPS
    if "flip" in splitParts:
        print(str(number) + " Used Flip")
        results = ["Heads!", "Tails!"]
        processText(number, rand.choice(results))
        return True
    if "rps" in splitParts:
        expressions = ["Rock", "Paper", "Scissors"]
        computerChoice = rand.randint(0, 2)
        userChoice = None
        for (i, expr) in enumerate(expressions):
            if expr.lower() in splitParts:
                userChoice = i

        if userChoice is None:
            processText(number, "Send rps with 'rock', 'paper', or 'scissors' to play")
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

        processText(number, response + result)
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
            userNum = trimNumber(number)
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
                processText(number, formatResp(basicInfo, advancedInfo, allFlag))
        else:
            processText(number, "Invalid Team Number")
            return False
    else:
        refDB = db.reference('Phones')
        phoneDB = refDB.order_by_key().get()
        userNum = trimNumber(number)
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
                    processText(number, formatResp(basicInfo, advancedInfo, allFlag))
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
                processText(number, formatResp(matchStr, "", 0))
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
                    processText(number, "The requested team was not in the match or is missing info")
                else:
                    processText(number, formatResp(matchStr, "", 0))
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
                processText(number, matchStr)
                matchR = requests.get(apiURL + "match/" + maxMatch, headers=apiHeaders)
                matchStr = "Best game: "
                if maxStation == 10 or maxStation == 11 or maxStation == 12 or maxStation == 13 or maxStation == 14:
                    matchStr += redcompileinfo(matchR.json())
                else:
                    matchStr += bluecompileinfo(matchR.json())
                processText(number, matchStr)
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
                    processText(number, matchStr)
                if sndMatch != "":
                    matchR = requests.get(apiURL + "match/" + sndMatch, headers=apiHeaders)
                    matchStr = "2nd best game: "
                    if sndStation == 10 or sndStation == 11 or sndStation == 12 or sndStation == 13 or sndStation == 14:
                        matchStr += redcompileinfo(matchR.json())
                    else:
                        matchStr += bluecompileinfo(matchR.json())
                    processText(number, matchStr)
                if thirdMatch != "":
                    matchR = requests.get(apiURL + "match/" + thirdMatch, headers=apiHeaders)
                    matchStr = "3rd best game: "
                    if thirdStation == 10 or thirdStation == 11 or thirdStation == 12 or thirdStation == 13 or thirdStation == 14:
                        matchStr += redcompileinfo(matchR.json())
                    else:
                        matchStr += bluecompileinfo(matchR.json())
                    processText(number, matchStr)
            else:
                processText(number,
                         "Incorrect format. Use ?:matchinfo or helpme:matchinfo for information on how to use this command")
        except IndexError:
            processText(number,
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
    global rateLimit
    global autoSum
    global teleOpSum
    global helpNumList
    if number in adminList:
        if "freeze" in msg:  # Disable or enable
            print("Admin " + str(number) + " used the freeze command")
            if disableMode == 0:
                disableMode = 1
                processText(number, "Disable mode Enabled!")
                print("Disable mode - on")
            else:
                disableMode = 0
                processText(number, "Disable mode Disabled!")
                print("Disable mode - off")
            return True
        elif "updateadmins" in msg:
            print("Admin " + str(number) + " used the updateAdmins command")
            loadAdminList()
            return True
        elif "checkstatus" in msg:
            print("Admin " + str(number) + " used the checkStatus command")
            processText(number, "TOAText is online and you are on the admin list!")
            return True
        elif "pingme" in msg:
            print("Admin " + str(number) + " used the pingme command")
            if number in pingList:
                pingList.remove(number)
                processText(number, "Removed from ping list")
            elif number not in pingList:
                pingList.append(number)
                processText(number, "Added to ping list")
            return True
        elif "joinhelp" in msg:
            print("Admin " + str(number) + " used the joinHelp command")
            if number in helpNumList:
                helpNumList.remove(number)
                processText(number, "Removed from help list")
            elif number not in helpNumList:
                helpNumList.append(number)
                processText(number, "Added to help list")
            return True
        elif "sendhelp" in msg:
            print("Admin " + str(number) + " used the sendHelp command")
            splitParts = rawRequest.lower().replace(" ", " ").split(":")
            processText(str(splitParts[1]), "From admin - " + str(splitParts[2]))
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
            processText(number, formatResp(str(totalStatus), "", 0))
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
        elif "currentinfo" in msg or "champinfo" in msg:
            totalLiveAlertUsers = 0
            curStr = "Alerts: \n"
            refDB = db.reference('liveEvents/1819-CMP-DET1')
            phoneDB = refDB.order_by_key().get()
            totalLiveAlertUsers += len(phoneDB)
            curStr += "Users in Edison: " + str(len(phoneDB)) + "\n"
            refDB = db.reference('liveEvents/1819-CMP-DET2')
            phoneDB = refDB.order_by_key().get()
            totalLiveAlertUsers += len(phoneDB)
            curStr += "Users in Ochoa: " + str(len(phoneDB)) + "\n"
            curStr += "Total: " + str(totalLiveAlertUsers)
            processText(number, curStr)
            return True
        elif 'ratelim' in msg or 'rl' in msg:
            for split in msg:
                if split.isdigit():
                    rateLimit = int(split)
                    break
            else:
                rateLimit = 2
            if rateLimit > 50:
                rateLimit = 50
            processText(number, "Rate limit set to " + str(rateLimit))
            return True
        elif 'queueinfo' in msg:
            with open("queue.json", "r") as read_file:
                data = json.load(read_file)
            processText(number, "There are " + str(len(data["queue"])) + " messages in the queue. The number of allowed queued messages in Twilio is " + str(rateLimit))
            return True
        elif 'clearqueue' in msg or 'clq' in msg:
            with open("queue.json", "r") as read_file:
                data = json.load(read_file)
            try:
                data["queue"] = []
                processText(number, "The queue has been cleared!")
            except:
                processText(number, "There was an error clearing the queue.")
            return True
    if number in eventAdminList:
        if "metrics" in msg or "metrix" in msg:
            print("Admin " + str(number) + " used the metrics command")
            processText(number, metricGet())
            processText(number, metricTwoGet())
            processText(number, TOAMetrics())
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
    metricStr += "TeamAvg reqs - " + str(data["avgGet"]) + "; "
    metricStr += "Match info reqs - " + str(data["matchGet"]) + "; "
    metricStr += "Live Alerts sent - " + str(data["livesSent"]) + "; "
    metricStr += "OPR reqs - " + str(data["oprGet"]) + "; "
    return metricStr

def TOAMetrics():
    metricStr = ""
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    metricStr += "TOAText users - " + str(len(phoneDB)) + "; "
    refDB = db.reference('Users')
    userDB = refDB.order_by_key().get()
    metricStr += "myTOA users - " + str(len(userDB))
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
    global sesAccessKeyId
    global sesSecretAccessKey
    with open("twilio.json", "r") as read_file:
        data = json.load(read_file)
    twilioAuth = str(data["twilioAuth"])
    twilioAccountID = str(data["twilioID"])
    apiHeaders = {'content-type': 'application/json',
                  'X-TOA-KEY': str(data["toaKey"]),
                  'X-Application-Origin': 'TOAText'}
    functionsHeaders = {'Authorization': str(data["functionKey"])}
    webhookKey = str(data["webhookKey"])
    sesAccessKeyId = str(data["sesAccessKeyId"])
    sesSecretAccessKey = str(data["sesSecretAccessKey"])

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
        userNum = trimNumber(number)
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
                processText(number, firstMsg)
            else:
                print("That user exists and has no user ID")
        except:
            processText(number, "Your phone number has not been linked to a myTOA profile (EC4)")
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
            processText(number, teamStr)
        else:
            processText(number, "You have not set any favorite teams in your myTOA profile!")
        return True

def sendMass(splitParts, rawMsg, requester):
    if "massmsg" in splitParts and requester in adminList:
        refDB = db.reference('Phones')
        phoneDB = refDB.order_by_key().get()
        for number in phoneDB:
            try:
                if phoneDB[number]["msgopt"]:
                    processText("+" + number, rawMsg.replace("massmsg ", ""), False)
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
                processText(str(userNum), str(userMsg), False)
            print(userMsg)
            return True
        except KeyError:
            processText(requester, "This eventmsg was not sent!")
            return True
        except ValueError:
            processText(requester, "This eventmsg was not sent!")
            return True
        except AttributeError:
            processText(requester, "This eventmsg was not sent!")
            return True

def optOutIn(userNum, splitParts):
    refDB = db.reference('Phones')
    phoneDB = refDB.order_by_key().get()
    number = userNum
    userNum = trimNumber(userNum)
    if userNum not in phoneDB:
        refDB.child(userNum).set({'opted': True, 'msgopt': False})
        print("Phone number added to DB")
        refDB = db.reference('Phones')
        phoneDB = refDB.order_by_key().get()
        processText(number, "Welcome to TOAText! Send 'help' to receive a list of commands and how to use them! Send STOP to opt out of TOAText and send START to join back in")
    if "quit" in splitParts or "stop" in splitParts:
        refDB.child(userNum).update({'opted': False})
        processText(number, "You have now opted out of ALL TOAText messages. Send START to rejoin", True)
        print(str(userNum) + " has opted out")
        return True
    elif "start" in splitParts:
        refDB.child(userNum).update({'opted': True})
        processText(number, "You have now rejoined TOAText and can use all the features")
        return True
    if 'msgopt' in splitParts:
        if not phoneDB[userNum]['msgopt']:
            refDB.child(userNum).update({'msgopt': True})
            processText(number, "You are now opted back into TOAText annoucements!")
        else:
            refDB.child(userNum).update({'msgopt': False})
            processText(number, "You have been opted out of all TOAText mass annoucements (Note: This does not include live alert annoucements)")
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
            processText(str(num), str(adminList), True)
    textSend = sendText("textSend")
    textSend.start()
    app.run(host='0.0.0.0', port=5001)