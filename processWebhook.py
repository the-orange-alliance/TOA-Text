import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import requests

import config
import twilioInterface as textI

def liveAlerts(alertJson):
    userMsg = ""
    matchInfo = alertJson
    refDB = db.reference('liveEvents')
    eventsDB = refDB.order_by_key().get()
    userMsg += str(matchInfo['message_data']["event_key"]) + " "
    if int(matchInfo['message_data']["red_score"]) > int(matchInfo['message_data']["blue_score"]):
        userMsg += str(matchInfo['message_data']["match_name"]) + " went to the red alliance! "
    elif int(matchInfo['message_data']["red_score"]) < int(matchInfo['message_data']["blue_score"]):
        userMsg += str(matchInfo['message_data']["match_name"]) + " went to the blue alliance! "
    elif int(matchInfo['message_data']["red_score"]) == int(matchInfo['message_data']["blue_score"]):
        userMsg += str(matchInfo['message_data']["match_name"]) + " was a tie! "
    else:
        userMsg += str(matchInfo['message_data']["match_name"]) + " just ended! "
    personR = requests.get(config.apiURL + "match/" + matchInfo['message_data']['match_key'] + "/participants",
                           headers=config.apiHeaders)
    redList = []
    blueList = []
    for i in range(len(personR.json())):
        if personR.json()[i]["station"] < 19:
            redList.append(int(personR.json()[i]["team_key"]))
        elif personR.json()[i]["station"] > 19:
            blueList.append(int(personR.json()[i]["team_key"]))
    userMsg += str(matchInfo['message_data']["red_score"]) + " red " + str(redList) + ", "
    userMsg += str(matchInfo['message_data']["blue_score"]) + " blue " + str(blueList) + " "
    if matchInfo['message_data']['match_key'] not in config.recievedMatchKeys:
        config.recievedMatchKeys.append(matchInfo['message_data']['match_key'])
        for userNum in eventsDB[matchInfo['message_data']["event_key"]]:
            savedInfo = eventsDB[matchInfo['message_data']["event_key"]][userNum]
            if savedInfo['global'] and len(savedInfo) == 1:
                textI.sendText("+" + userNum, userMsg)
            elif savedInfo['global']:
                for teams in savedInfo.keys():
                    if teams == 'global':
                        continue
                    try:
                        if int(teams) in redList or int(teams) in blueList:
                            textI.sendText("+" + userNum, "[Team " + str(teams) + " Alert] " + userMsg)
                            break
                    except:
                        break
                else:
                    textI.sendText("+" + userNum, userMsg)
            elif not savedInfo['global'] and len(savedInfo) > 1:
                for teams in savedInfo.keys():
                    if teams == 'global':
                        continue
                    if teams in redList or teams in blueList:
                        textI.sendText("+" + userNum, "[Team " + str(teams) + " Alert] " + userMsg)
                        break