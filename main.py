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

app = Flask(__name__)
if __name__ == "__main__":  # starts the whole program
    print("started")
    fileIO.loadAPIKeys()
    app.run(host='0.0.0.0', port=5001)