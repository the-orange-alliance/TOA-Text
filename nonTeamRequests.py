#External imports
import random as rand
import requests

#Internal imports
import config
import firebase

def help(msg, number):
    team_command_descriptions = {
        "info": "returns basic information on a team, such as name, location, rookie year, and website",
        'events': 'returns all events that a team has completed in a season',
        'awards': 'returns all awards that a team has won in the current season',
        'matchInfo': 'returns all matches a team has participated in OR a match breakdown, depending on usage',
        'OPR': "returns a team's average OPR from the current season",
        'avgScore': "returns a team's average alliance score from the current season"
    }
    nonteam_command_descriptions = {
        "help": "brings up a list of available commands",
        "about": "provides information about TOAText",
        "myTOA": "if a myTOA account is linked, provides account information",
        "pickup": "returns FTC/Robotics related pickup lines",
        "addLive": "adds the user to the live alerts for a specified event",
        "streams": "responds with all live streams on TOA",
        "flip": "flips a coin",
        "roll": "rolls a die",
        "searchTN": "searches for a team number by using a team name"
    }
    admin_command_descriptions = {
        "metrics": "returns TOAText metrics",
        "serverStatus": "returns information about server status",
        "ss": "returns information about server status",
        'updateAdmins': "updates admin list through myTOA and firebase",
        "clearLive": "removes all users from the specified live event",
        "massMsg": "messages all TOAText users still opted in"
    }
    #print("Help")
    def respond_by_command(descriptions, splitParts, number):
        for command, description in descriptions.items():
            if command in splitParts:
                return [str(command + ' - ' + description)]
        return False
    if 'help' in msg or '?' in msg or 'sendhelp' in msg:
        sent = False
        if number in config.adminList:
            sent = respond_by_command(admin_command_descriptions, msg, number)
        if not sent:
            sent = respond_by_command(team_command_descriptions, msg, number)
        if not sent:
            sent = respond_by_command(nonteam_command_descriptions, msg, number)
        if not sent:
            helpList = []
            if number in config.adminList:
                keyStr = ''
                for key in admin_command_descriptions.keys():
                    keyStr += str(key) + ", "
                helpList.append("Admin commands - " + keyStr[:-2])
            keyStr = ''
            for key in nonteam_command_descriptions.keys():
                keyStr += str(key) + ", "
            helpList.append("Non-team commands - "+ keyStr[:-2])
            keyStr = ''
            for key in team_command_descriptions.keys():
                keyStr += str(key) + ", "
            helpList.append("Team commands - "+ keyStr[:-2])
            helpList.append("Begin text with team number and then spaces or : to separate commands. Send a team number with nothing else to be provided a brief overview")
            return helpList
    return False

def about(msg, number):
    #print("About")
    if "about" in msg:
        return ["TOAText is a portable, on-the-go version of The Orange Alliance. It can provide information about teams, along with statistics", "To know more about any commands, use ?:[command] or help:[command]"]
    return False

def myTOA(msg, number):
    if 'mytoa' in msg:
        return firebase.myTOA(msg, number)
    return False

def pickupLines(msg, number):
    #print("Pickup Lines")
    if "pickup" in msg:
        pickupList = ["Baby, are you FTC? Because everyone overlooks you and they shouldn't",
                      "Are you a tank drive? Cause I'd pick you every time",
                      "Are you a rivet, because without you I'd fall apart",
                      "Don't call me Java, because I'll never treat you like an object",
                      "Baby are you a swerve drive 'cause you spin me right round",
                      "Are you a compass?  Because you're a-cute and I love having you around",
                      "Hey baby, are you a soldering iron because I melt when I see you", "You're FIRST in my heart",
                      "Are you FTC? Because I'll care about you when nobody else will",
                      "Are you a robot, cause you just drove away with my heart",
                      "Not in elims? You're always the first seed in my heart!!",
                      "Are you hook and loop tape? Because I think I'm stuck on you",
                      "Do you want to be my capstone, because you multiply my happiness"]
        randomNum = rand.randint(0, len(pickupList) - 1)
        return [pickupList[randomNum]]
    return False

def addLive(msg, number):
    #print("Add live")
    if 'addlive' in msg:
        return ["This command is currently a WIP"]
    return False

def streams(msg, number):
    #print("Live streams")
    if 'stream' in msg or 'streams' in msg:
        r = requests.get(config.apiURL + "streams",
                         headers=config.apiHeaders)
        resp = r.json()
        streamList = []
        print(resp)
        for stream in resp:
            streamList.append(str(stream["stream_name"]) + " - " + stream["url"])
        return streamList
    return False

def flip(msg, number):
    #print("Flip a coin")
    if "flip" in msg:
        ansList = ["heads!", "tails!"]
        ans = "The coin landed on " + str(ansList[rand.randint(0,1)])
        return [ans]
    return False

def roll(msg, number):
    #print("Roll a die")
    if "roll" in msg:
        ans = "You rolled a " + str(rand.randint(1,6))
        return [ans]
    return False

def searchTN(msg,number):
    if 'searchtn' in msg:
        return ["This command is currently a WIP"]
    return False