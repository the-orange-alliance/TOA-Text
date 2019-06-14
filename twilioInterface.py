#External imports
from twilio.rest import Client

#Internal imports
import config

def sendText(number, msg):
    client = Client(config.twilioAccountID, config.twilioAuth)
    if "+1" in number:
        message = client.messages \
            .create(
            body=str(msg),
            from_='+16146666924',
            to=str(number)
        )
    elif "+972" in number:
        message = client.messages \
            .create(
            body=str(msg),
            from_='+972525932576',
            to=str(number)
        )

