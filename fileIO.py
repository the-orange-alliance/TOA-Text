#External imports
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from dotenv import load_dotenv
import os

#Internal imports
import config

def loadAPIKeys():  # Loads Twilio account info off twilio.json
  load_dotenv()
  with open("twilio.json", "r") as read_file:
      data = json.load(read_file)
  config.twilioAuth = str(data["twilioAuth"])
  config.twilioAccountID = str(data["twilioID"])
  config.apiHeaders = {'content-type': 'application/json',
                'X-TOA-KEY': str(data["toaKey"]),
                'X-Application-Origin': 'TOAText'}
  config.functionsHeaders = {'Authorization': str(data["functionKey"])}
  config.webhookKey = str(data["webhookKey"])


