import requests
import time

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ircTimeout import TwitchChatIRC

from configparser import ConfigParser

import re

config = ConfigParser()
config.read('conf.ini')

sender_email = config['email']['gmail_send']
sender_password = config['email']['gmail_key']
receiver_email = config['email']['email_recv']

smtp_server = "smtp.gmail.com"
smtp_port = 587

homepage = requests.get("https://www.twitch.tv").text
pattern = r'clientId="([a-zA-Z0-9]+)"'
match = re.search(pattern, homepage).group(1)
clientId = match


def sendMail(streamer):
    subject = "Twitch Gql Viewer"
    body = "Detected"+ config['victim']['id'] +"in : " + streamer
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        print("send email to "+receiver_email)
    except Exception as e:
        print("email sending error occurred: ", str(e))

def getFollowList(streamerList):
    victim = config['victim']['id']
    url = 'https://followholic.pages.dev/api/follow/'+victim+'/?cursor='
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            streamerList = [item['login'] for item in data['channels']]
            return streamerList
        else:
            print('api is not okay now')
            return streamerList
    except:
        print('buffering List')
        return streamerList

def twitchView(streamerList):
    url = 'https://gql.twitch.tv/gql'
    headers = {
            'Client-Id': clientId,
            'Content-Type': 'application/json'
        }
    payload = []
    for streamerId in streamerList:
        payload.append(
            {
                "operationName": "CommunityTab",
                "variables": {
                    "login": streamerId
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "2e71a3399875770c1e5d81a9774d9803129c44cf8f6bad64973aa0d239a88caf"
                    }
                }
            }
        )
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                if 'chatters' in item['data']['user']['channel']:
                    viewers = item['data']['user']['channel']['chatters']['viewers']
                    if any(chatter['login'] == config['victim']['id'] for chatter in viewers):
                        sendMail(item['data']['user']['channel']['name'])
                        captureChat(item['data']['user']['channel']['name'])
                        break
            time.sleep(30)
        else:
            print('API call failed:', response.status_code)
    except:
        print('buffering')

def captureChat(streamer):
	twitch_chat_irc = TwitchChatIRC()
	twitch_chat_irc.listen(streamer)
	twitch_chat_irc.close_connection()

streamerList = getFollowList([])
while True:
    streamerList = getFollowList(streamerList)
    for i in range(60):
        twitchView(streamerList)
        time.sleep(1)