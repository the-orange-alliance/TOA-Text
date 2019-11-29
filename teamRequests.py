#external imports
import requests

#internal imports
import config

def basicInfo(msg, number):
    #print("Basic team info")
    for part in msg:
        if part.isdigit():
            team = part
            break
    else:
        return False
    r = requests.get(config.apiURL + "team/" + team,
                     headers=config.apiHeaders)
    resp = r.json()
    teamStr = ''
    teamStr += str(resp[0]["team_number"]) + " - "
    teamStr += resp[0]["team_name_short"] + ", "
    teamStr += "Rookie Year: " + str(resp[0]["rookie_year"]) + ", "
    teamStr += "Location: " + resp[0]["city"] + " " + resp[0]["state_prov"] + ", "
    teamStr += "Website: " + resp[0]["website"]
    return [teamStr]


def events(msg, number):
    #print("All events for the given season")
    if 'events' in msg:
        for part in msg:
            if part.isdigit():
                team = part
                break
        else:
            return False
        r = requests.get(config.apiURL + "team/" + team + "/events/"+config.seasonKey,
                         headers=config.apiHeaders)
        # print(r.text)
        advInfoString = "Events - "
        for i in r.json():
            # print(r.json()[r.json().index(i)]["event_key"])
            eventr = requests.get(config.apiURL + "event/" + r.json()[r.json().index(i)]["event_key"], headers=config.apiHeaders)
            advInfoString += eventr.json()[0]["event_name"] + ", "
        return [advInfoString[:-2]]
    return False

def awards(msg, number):
    print("All awards for the given season")
    if 'awards' in msg:
        for part in msg:
            if part.isdigit():
                team = part
                break
        else:
            return False
        r = requests.get(config.apiURL + "team/" + team + "/awards/" + config.seasonKey,
                         headers=config.apiHeaders)
        advInfoString = "Awards - "
        prevevent_name = ""
        firstRun = True
        addFinal = False
        loopCount = 0
        for i in r.json():
            loopCount += 1
            print(r.json()[r.json().index(i)]["award_name"])
            eventr = requests.get(config.apiURL + "event/" + r.json()[r.json().index(i)]["event_key"], headers=config.apiHeaders)
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
        return [advInfoString]
    return False

def matchInfo(msg,number):
    #print("Match breakdown by category")
    if 'matchinfo' in msg:
        return ["This command is currently a WIP"]
    return False

def opr(msg, number):
    #print("OPR per event")
    if 'opr' in msg:
        for part in msg:
            if part.isdigit():
                team = part
                break
        else:
            return False
        r = requests.get(config.apiURL + "team/" + team + "/results/" + config.seasonKey,
                         headers=config.apiHeaders)
        resp = r.json()
        OPRavg = 0
        maxOPR = 0
        for event in resp:
            OPRavg += event["opr"]
            if event["opr"] > maxOPR:
                maxOPR = event["opr"]
        OPRavg = OPRavg/len(resp)
        print(OPRavg)
        return[str("This teams average OPR for the current season is " + str(OPRavg)),str("This teams max OPR for the current season is " + str(maxOPR))]
    else:
        return False

def avgscore(msg, number):
    print("Average team alliance scores")
    if 'avgscore' in msg:
        return ["This command is currently a WIP"]
    return False

