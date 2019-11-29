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

if __name__ == "__main__":  # starts the whole program
    print("started")
    fileIO.loadAPIKeys()
    firebase.loadAdminNums()
    textI.sendText(config.adminList[3],"TOAText 2.0 has booted up")
    app.run(host='0.0.0.0', port=5001)
