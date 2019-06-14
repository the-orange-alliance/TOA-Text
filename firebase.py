#External imports
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

#Internal imports
import config

cred = credentials.Certificate('TOAFirebase.json')
default_app = firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://the-orange-alliance.firebaseio.com/'
    })
