#External Imports
import random as rand

#internal Imports
import nonTeamRequests as nTR
import teamRequests as tR
import adminRequests as aR
import twilioInterface as textI

def checkTeam(msg, number):
    splitMsg = parseMessage(msg)
    response = False
    functList = [adminRequests,nonTeamRequests,teamRequests]
    for funct in functList:
        response = funct(msg, number)
        if response is not False:
            break
    if response is False:
        errorList = ["Whoops. Someone must've forgotten to use a grounding strap!", "This is really grinding my gears",
                     "I must be a swerve drive, because apparently I never work!",
                     "Hey there! Thats not very nice of you!",
                     "Just remember, goBILDA or go home", "... Bestrix.",
                     "Hold your horses, that's not very GP of you",
                     "Try again. The delivery robot strafed the wrong direction",
                     "I'm still waiting... and waiting... and waiting"]
        randomNum = rand.randint(0, len(errorList) - 1)
        textI.sendText(number,errorList[randomNum])
    else:
        for str in response:
            textI.sendText(number,str)
    return

def teamRequests(msg, number):
    response = False
    functList = []
    for funct in functList:
        response = funct(msg, number)
        if response is not False:
            break
    return response

def nonTeamRequests(msg, number):
    response = False
    functList = [nTR.help, nTR.about, nTR.pickupLines, nTR.myTOA, nTR.addLive,nTR.streams,nTR.flip,nTR.roll,nTR.searchTN]
    for funct in functList:
        response = funct(msg, number)
        if response is not False:
            break
    return response

def adminRequests(msg, number):
    response = False
    functList = [aR.clearLive,aR.metrics,aR.serverStatus,aR.updateAdmins]
    for funct in functList:
        response = funct(msg, number)
        if response is not False:
            break
    return response

def parseMessage(msg):
    merge_expression_groups = [
        ("a","b"),
        ("c","d")
    ]
    if ':' in msg:
        return msg.lower.replace(" ","").split(':')
    else:
        splitParts = msg.lower().split(" ")
        for expr_group in merge_expression_groups:
            for i in range(0, len(splitParts) - len(expr_group) + 1):
                sublist = splitParts[i:i + len(expr_group)]
                if tuple(sublist) == expr_group:
                    for n in range(i + 1, i + len(expr_group)):
                        splitParts.pop(n)
                    splitParts[i] = ''.join(expr_group)
                    break
        return splitParts
