#!/usr/bin/env python3

# python3 program to log temperature and humidity data to Google Drive
# and send email alerts if results are above a threshold using
# Adafruit_DHT library
# Matthew Perry 2019-4-24

import pickle
import base64
import httplib2
import Adafruit_DHT
import time
import json
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/gmail.send']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = 'Enter spreadsheet ID here'
RANGE_NAME = 'Sheet1'

sensor = Adafruit_DHT.DHT22
pin = 23


def getCredential():
    # returns a google api credential object
    credential = None

    credentialDirectory = Path.home() / '.credentials'
    clientSecretPath = credentialDirectory / 'google_api_credential.json'
    tokenPath = credentialDirectory / 'token.pickle'

    if not clientSecretPath.exists():
        print("No client secret file found. Please place your client ' \
            'secret json file in '~/.credetials/google_api_credential.json'")
        exit()

    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if tokenPath.exists():
        with tokenPath.open(mode='rb') as token:
            credential = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not credential or not credential.valid:
        if credential and credential.expired and credential.refresh_token:
            credential.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                   str(clientSecretPath), SCOPES)
            credential = flow.run_console()
        # Save the credentials for the next run
        tokenPath.touch(exist_ok=True)
        with tokenPath.open(mode='wb') as token:
            pickle.dump(credential, token)

    return credential


def sendMessage(emailMessage, credential):
    emailBody = formatMessage(emailMessage)
    gmailService = build('gmail', 'v1', credentials=credential)

    try:
        email = gmailService.users().messages().send(userId='me',
                                                     body=emailBody).execute()
        return email
    except errors.HttpError as error:
        print ("Error sending email.")
        return error


def formatMessage(emailMessage):
    message = MIMEText(emailMessage['message'])
    message['to'] = emailMessage['to']
    message['from'] = emailMessage['from']
    message['subject'] = emailMessage['subject']

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    emailBody = {'raw': raw_message}
    return emailBody


def logToGSheet(enviroData, credential):
    sheets = build('sheets', 'v4', credentials=credential).spreadsheets()

#   set values to append to spreadsheet
    values = [
        [
            enviroData['timeStamp'].strftime("%Y-%m-%d %H:%M:%S"),
            round(enviroData['temperature'] * 1.8 + 32, 1),
            round(enviroData['humidity'], 1)
        ]
    ]
    body = {
        'values': values
    }
    try:
        result = sheets.values().append(spreadsheetId=SPREADSHEET_ID,
                                        range=RANGE_NAME,
                                        valueInputOption='RAW',
                                        body=body).execute()
        return result
    except errors.HttpError as error:
        print("Unable to append data to Google Sheets")
        return error


def getEnviroData(enviroData):
    newHumidity, newTemperature = Adafruit_DHT.read(sensor, pin)

    if newHumidity is not None:
        enviroData['humidity'] = newHumidity
        enviroData['timeStamp'] = datetime.now()

    if newTemperature is not None:
        enviroData['temperature'] = newTemperature
        enviroData['timeStamp'] = datetime.now()

    return enviroData


def checkJSON(enviroData):
    httpDataFile = Path('/var/www/html/environmental.json')
    with httpDataFile.open() as jsonFile:
        jsonData = json.loads(jsonFile.read())

    if not jsonData['temperature'] == enviroData['temperature'] or \
       not jsonData['humidity'] == enviroData['humidity']:
        jsonData['temperature'] = enviroData['temperature']
        jsonData['humidity'] = enviroData['humidity']

        jsonDumps(jsonData, httpDataFile)


def jsonDumps(jsonData, httpDataFile):
    with httpDataFile.open(mode='w') as jsonFile:
        httpDataFile.write_text(json.dumps(jsonData))


def main():

    credential = getCredential()
    enviroData = {'temperature': None,
                  'humidity': None,
                  'timeStamp': datetime.now()}

    emailMessage = {'message': 'Enter email text here',
                    'to': 'to_address',
                    'from': 'from_address',
                    'subject': 'Enter subject here'}

    while enviroData['temperature'] is None or enviroData['humidity'] is None:
        enviroData = getEnviroData(enviroData)

    checkJSON(enviroData)

    lastUpdate = datetime.now()
    time.sleep(2)

    while True:

        enviroData = getEnviroData(enviroData)

        now = datetime.now()
        diff = now - lastUpdate
        if diff.seconds > 30:
            lastUpdate = datetime.now()
            if not credential.valid:
                credential = getCredential()

            logToGSheet(enviroData, credential)

            checkJSON(enviroData)

            # TODO create humidity and temperature thresholds and send email
            # alerts when those thresholds are exceeded.

        time.sleep(2)


if __name__ == '__main__':
    main()
