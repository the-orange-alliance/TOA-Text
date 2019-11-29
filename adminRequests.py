#external imports
import requests

#internal imports
import config
import firebase

def metrics(msg, number):
    if "metrics" in msg:
        return ["This command is currently disabled","Pt2 is also disabled"]
    return False

def serverStatus(msg, number):
    if "serverstatus" in msg or "ss" in msg:
        r = requests.get(config.functionsURL + "serverStatus", headers=config.functionsHeaders)
        resp = r.json()
        totalStatus = ""
        for x in range(len(resp)):
            procName = resp[x]["name"]
            procID = resp[x]["pm_id"]
            procStat = resp[x]["pm2_env"]["status"]
            totalStatus += str(procName) + "(" + str(procID) + ") is " + str(procStat) + "; "
        return [totalStatus]
    return False

def updateAdmins(msg, number):
    if 'searchtn' in msg:
        firebase.loadAdminNums()
        return ["Admins updated"]
    return False

def clearLive(msg, number):
    #print("Clear live event")
    if 'clearlive' in msg:
        return ["This command is currently a WIP"]
    return False

def massMsg(msg,number):
    #print("Send message to ALL opted in TOAText Users")
    if 'massmsg' in msg:
        return ["This command is currently a WIP"]
    return False
