from __future__ import print_function
import logging
import httplib2
import time
import base64
import json
import datetime
from apiclient import discovery
import oauth2client
from googleapiclient.errors import HttpError
from oauth2client import client
from oauth2client import tools
## pip install httplib2 google-api-python-client

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

FRESH_TIME = 180

class MonitoredSystem:
    def __init__(self, system, num_warning, num_errors, init=False, timestamp = False):
        self.system = system
        self.num_warnings = num_warning
        self.num_errors = num_errors
        self.checkdate = datetime.datetime.now()
        self.is_fake = init
        self.timestamp = timestamp ## datetime object

    def get_state(self):
        ## TODO: Maak hier een configuratie optie van
        if((self.checkdate + datetime.timedelta(0, 60 * 30) <  datetime.datetime.now()) or self.is_fake):
            return "STALE"
        elif self.num_errors > 0:
            return "ERROR"
        elif self.num_warnings > 0:
            return "WARNING"
        else:
            return "OK"

    def is_fresh(self):
        if self.timestamp:
            return self.timestamp > datetime.datetime.now()-datetime.timedelta(minutes=FRESH_TIME)
        else:
            return False

monitored_systems = {}

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/gmail-python-quickstart.json
SCOPES = 'https://mail.google.com/'
CLIENT_SECRET_FILE = 'client_id.json'
APPLICATION_NAME = 'qfors-monitor'
monitored_label = "MONITORING"
monitored_failed_label = "MONITORING_FAILED"
labelcache = {}


## Add expected systems
#monitored_systems["ALU_OTA"] = MonitoredSystem("ALU_OTA",0,0,True)
#monitored_systems["AHOLD_OTAP"] = MonitoredSystem("AHOLD_OTAP",0,0,True)

logger = logging.getLogger()

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    credential_path = 'gmail-python-quickstart.json'

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def retrieve_monitor_from_message(messagemeta, service):
    returnVal = False

    num_warnings = 0
    num_errors = 0

    mailid = messagemeta["id"]

    ## Haal nu de bericht inhoud op van de gevoonden berichten
    try:
        message = service.users().messages().get(userId='me', id=mailid).execute()
        ##pprint(message)

        if "data" in message['payload']["body"]:
            msg_str = base64.urlsafe_b64decode(message['payload']["body"]["data"].encode("ascii"))
            ## Nope, we hebben multipart content gehad. Zal de eerste wel zijn..
        else:
            msg_str = base64.urlsafe_b64decode(message['payload']["parts"][0]["body"]["data"].encode("ascii"))
        ## Parsed JSON content
        try:
            msg_str = msg_str.replace("\\", "_")
            j = json.loads(msg_str, strict=False)

            ## Got JSON
            most_recent = False
            for alert in j["alert"]:
                if alert["severity"] == "Critical":
                    num_errors += 1
                elif alert["severity"] == "Warning":
                    num_warnings += 1
                    ## 27-08-2015 12:57:48
                timestamp = datetime.datetime.strptime(alert["timestamp"], '%d-%m-%Y %H:%M:%S')
                if not most_recent or (timestamp > most_recent):
                    most_recent = timestamp
            system = j["client"]
            returnVal = MonitoredSystem(system, num_warnings, num_errors, timestamp=timestamp)
        except Exception, e:
            logger.error("Could not parse to JSON due to " + e.message)
    except HttpError as e:
        logger.debug("Could not load message, it could be already deleted: " + str(e))
    return returnVal


def retrieve_labelid(labelname, service):
    labelid = False
    if labelname in labelcache.keys():
        labelid = labelcache[labelname]
    else:
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])

        ## Scoor het ID van label
        if not labels:
            print('No labels found.')
        else:
          for label in labels:
            if label['name'] == labelname:
                labelid = label['id']
                labelcache[labelname] = labelid
                break;
    return labelid


last_date = 0
def get_monitoring_status():
    global last_date
    if time.time() - last_date > 59:
        """Shows basic usage of the Gmail API.

        Creates a Gmail API service object and outputs a list of label names
        of the user's Gmail account.
        """

        credentials = get_credentials()
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('gmail', 'v1', http=http)

        labelid = retrieve_labelid(monitored_label, service)
        ## Haal alle messages op met dat label ID
        results = service.users().messages().list(userId='me', labelIds=labelid).execute()
        messages = results.get('messages', [])
        if not messages:
            print('No messages with label found.')
        else:
            deleteables = []
            for messagemeta in messages:
                message = retrieve_monitor_from_message(messagemeta, service)
                if message:
                    deleteables.append(messagemeta['id'])
                    monitored_systems[message.system] = message
                    service.users().messages().delete(userId='me',id=messagemeta['id'])
                else:
                    ## Remove MONITORING label, add MONITORING_FAILED and return to the inboxinboxinbox
                    relabel = {'removeLabelIds': [retrieve_labelid(monitored_label, service)], 'addLabelIds': [retrieve_labelid(monitored_failed_label, service), retrieve_labelid("UNREAD", service), retrieve_labelid("INBOX", service)]}
                    service.users().messages().modify(userId='me', id=messagemeta['id'], body=relabel).execute()


            ## GOOGLE! WHY U NOT DELETE!
            if len(deleteables) > 0:
                logger.debug("Deleting " + str(len(deleteables)) + " messages..")
                service.users().messages().batchDelete(userId='me',body={'ids':deleteables})
                logger.debug("Done deleting ")

        last_date = time.time()
    return monitored_systems
