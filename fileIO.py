#External imports
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

#Internal imports
import config

def loadAPIKeys():  # Loads Twilio account info off twilio.json
    with open("twilio.json", "r") as read_file:
        data = json.load(read_file)
    config.twilioAuth = str(data["twilioAuth"])
    config.twilioAccountID = str(data["twilioID"])
    config.apiHeaders = {'content-type': 'application/json',
                  'X-TOA-KEY': str(data["toaKey"]),
                  'X-Application-Origin': 'TOAText'}
    config.functionsHeaders = {'Authorization': str(data["functionKey"])}
    config.webhookKey = str(data["webhookKey"])

