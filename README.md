# TOA-Text
SMS based team and event search through [The Orange Alliance](https://theorangealliance.org)

This project utilizes the following resources:

 - Python 3.7
 - Flask
 - Twilio API
 - TOA API

## About

TOA-Text utilizes the Twilio API to recieve and send SMS (text) messages. These messages are processed in the TOA-Text backend for content such as team based requests, non-team based requests, or admin requests. Then, using the TOA API, the request in processed and formatted before being sent back out in a series of 1-3 SMS messages.

This service helps combat the lack of internet at some *FIRST* Tech Challenge events through the lack of need for internet connectivity.

##  Help

To begin, send an SMS message to (614) 666 - 6924 containing "help". From there, a list of available commands and instructions will be sent to your phone
