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