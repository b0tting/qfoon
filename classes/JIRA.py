import datetime
import os
import shutil

import logging
import traceback

import pytz
import requests
from dateutil import parser

class JiraQueryException(Exception):
    pass

class JiraParser:

    jiraapi = "/rest/api/2/search/"
    jiraissueapi = "/rest/api/2/issue/"
    jirauserapi = "/rest/api/2/user/assignable/search"

    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)
    requests.packages.urllib3.disable_warnings()

    # Niet okay! Zoveel parameters!
    def __init__(self, baseurl, username, password, teamdict, recent):

        self.jirabase = baseurl
        self.session = requests.Session()
        self.session.verify = False

        self.session.auth = (username, password)

        self.recenthours = 72
        self.recentminutes = recent

        # Mapping van keys op teams
        self.teamDict = teamdict

        self.operators = False
        self.operators_update = False

    def get_ticket_info(self, ticket):
        return self.get_jira_response(ticket, JiraParser.jiraissueapi, False)

    def get_ticket_exists(self, ticket):
        response = self.session.get(self.jirabase + self.jiraissueapi + ticket)
        return response.status_code == 200

    def get_jira_response(self, query, api = False, check_fields = True):
        if query.find("fields") == -1 and check_fields:
            query = query + "&fields=key,summary,created,reporter,assignee,issuetype,duedate,project,priority,parent,timetracking"

        if not api:
            api = JiraParser.jiraapi

        if api == JiraParser.jiraapi:
            query = "?jql=" + query

        logging.debug("Now fetching JIRA URL " + self.jirabase + api + query)
        response = self.session.get(self.jirabase + api + query)

        if(response.status_code == 400):
            logging.debug(response.text)
            raise JiraQueryException("Could not run query " + self.jirabase + api + query)
        return response.json()

    def get_jira_total(self, query):
        if query.find("fields") == -1:
            query = query + "&fields=key&maxResults=1"
        response = self.session.get(self.jirabase + self.jiraapi + "?jql=" + query)
        if(response.status_code == 400):
            logging.debug(response.text)
            raise JiraQueryException("Could not run query " + self.jirabase + self.jiraapi + "?jql=" + query)
        return response.json()["total"]

    def get_jira_data(self, query):
        data = self.get_jira_response(query)

        ## Now add recent info
        my_tz = "CET"
        tz = pytz.timezone(my_tz)
        today = datetime.datetime.today().date()
        recent = datetime.datetime.now(tz) - datetime.timedelta(minutes=self.recentminutes)
        if "issues" in data:
            for issue in data['issues']:
                if ("fields" in issue):
                    createdate = parser.parse(issue['fields']['created'])
                    issue['recent'] = (createdate > recent)

                    if createdate.date() == today:
                        issue["fields"]["created"] = createdate.strftime("%H:%M")
                    else:
                        issue["fields"]["created"] = createdate.strftime("%b %d")

                    key = issue["fields"]["project"]["key"].upper()
                    issue['team'] = self.teamDict[key] if key in self.teamDict.keys() else ""
        else:
            data["total"] = 0
        return data


    ## Caching JIRA images, because otherwise slow
    def get_jira_image(self, query, querystring):
        filename = "static/jiracache/" + str(query + "_" + querystring).translate(None, "/&=.")
        if not os.path.isfile(filename):
            logging.debug("Now fetching JIRA image URL " + self.jirabase + "/" + query + "?" + querystring)
            response = self.session.get(self.jirabase + "/" + query + "?" + querystring, stream=True)

            with open(filename, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
        else:
            logging.debug("Now fetching JIRA cached image " + self.jirabase + "/" + query + "?" + querystring)
        with open(filename, 'rb') as out_file:
            returnimage = out_file.read()

        return returnimage


    ## Also, caching operators
    def get_operator(self, username=False):
        checkdate = datetime.datetime.now() - datetime.timedelta(minutes=60)

        if not self.operators or checkdate > self.operators_update:
            ## Ik pak hier alle operators van het QFRS project. Dat is niet handig meer.
            self.operators = self.get_jira_response("?project=QFRS", JiraParser.jirauserapi, check_fields=False)
            self.operators_update = datetime.datetime.now()


        if username:
            current_operator = False
            for operator in self.operators:
                if operator["name"] == username:
                    current_operator = operator
                    break;
            return current_operator
        else:
            return self.operators


