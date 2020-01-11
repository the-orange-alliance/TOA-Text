#External imports
import requests
from twilio import twiml
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import random as rand
import threading
import json
from time import sleep
from flask import Flask, request, make_response
from fuzzywuzzy import fuzz
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

#Internal imports
import fileIO
import firebase
import twilioInterface as textI
import processTxt
import config
import processWebhook

app = Flask(__name__)

class incomingText(threading.Thread):  # Thread created upon request
    def __init__(self, name, sendnum, msgbody):
        threading.Thread.__init__(self)
        self.name = name
        self.sendnum = sendnum
        self.msgbody = msgbody
    def run(self):
        print("Fetching request to " + self.sendnum)
        processTxt.checkTeam(self.msgbody, self.sendnum)
        print("Finished request to " + self.sendnum)

class newAlert(threading.Thread):  # Thread created upon request
    def __init__(self, name, parsedJson):
        threading.Thread.__init__(self)
        self.name = name
        self.parsedJson = parsedJson
    def run(self):
        print("Starting live alert for " + self.name)
        processWebhook.liveAlerts(self.parsedJson)
        print("Finished live alert for " + self.name)

@app.route("/sms", methods=['POST'])
def receiveText():  # Code executed upon receiving text
    global numTwoList
    twilioNum = request.form['To']
    number = request.form['From']
    message_body = request.form['Body']
    resp = MessagingResponse()
    t = incomingText(number, number, message_body)
    t.start()
    return (str(resp))

@app.route("/receiveHook", methods=['POST'])
def newLiveAlerts(): #Captures generic match info
    if config.webhookKey == request.headers.get('webhookKey') or request.environ['REMOTE_ADDR'] == "127.0.0.1":
        matchInfo = request.get_json(force=True)
        print(matchInfo)
        if matchInfo['message_type'] != "match_scored":
            return 'wrong_type'
        t = newAlert(matchInfo['message_data']['match_key'], matchInfo)
        t.start()
        if config.webhookKey == request.headers.get('webhookKey'):
            resBody = '{"_code":200,"_message":"Key request successful"}'
        elif request.environ['REMOTE_ADDR'] == "127.0.0.1":
            resBody = '{"_code":200,"_message":"Localhost request successful"}'
    else:
        resBody = '{"_code":401,"_message":"Missing or invalid key"}'
    res = make_response(str(resBody))
    res.headers['Content-Type'] = 'application/json'
    print(resBody + " - " + str(request.environ['REMOTE_ADDR']))
    return res


if __name__ == "__main__":  # starts the whole program
    print("started")
    fileIO.loadAPIKeys()
    firebase.loadAdminNums()
    textI.sendText(config.adminList[3],"TOAText 2.0 has booted up")
    app.run(host='0.0.0.0', port=5001)