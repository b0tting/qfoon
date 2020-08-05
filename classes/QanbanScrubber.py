import sys

from datetime import date, datetime
import time


class QanbanScrubber():
    _timeparse = "%Y-%m-%d"
    daily_check_ops = ""

    def __init__(self, team_settings, jiraParser):
        self.settings = team_settings
        self.jiraParser = jiraParser
        self.jirausers = False

        ## Niet helemaal okay: ik misbruik een static var als instance var.
        daily_check_ops = self.settings["daily_check_reporter"]


    ## Sortering gebeurt in deze methode
    @staticmethod
    def ticket_list_compare(ticket1):
        if ticket1["fields"]["reporter"]["displayName"] in QanbanScrubber.daily_check_ops:
            returnval = 0
        elif not ticket1["fields"]["duedate"]:
            ## IK SPEEL VALS! Oei! Hogere prio's hebben nu een lager ID, maar dat is niet gegarandeerd!
            returnval = int(ticket1["fields"]["priority"]["id"]) + 2
        else:
            returnval = int(time.mktime(time.strptime(ticket1["fields"]["duedate"], QanbanScrubber._timeparse)))
        return returnval

    def qanban_scrub(self):
        ## PUT ZE HAMMER DOWN!
        issues_on_hold = self.jiraParser.get_jira_response(self.settings["query_onhold"])["issues"]
        allworking = self.jiraParser.get_jira_response(self.settings["query_working"])
        issues_in_q = self.jiraParser.get_jira_response(self.settings["query_open"])["issues"]
        try:
            issues_new_total = self.jiraParser.get_jira_total(self.settings["query_intake"])
        except Exception as e:
            issues_new_total = 0

        issues_working = {}
        for ticket in allworking["issues"]:
            assignee = ticket["fields"]["assignee"]["name"]
            if assignee not in issues_working:
                issues_working[assignee] = []
            issues_working[assignee].append(ticket)

        # Next, sort the buckets where relevant
        issues_in_q.sort(key=QanbanScrubber.ticket_list_compare)
        issues_on_hold.sort(key=QanbanScrubber.ticket_list_compare)
        for assigneeissues in issues_working.values():
            assigneeissues.sort(key=QanbanScrubber.ticket_list_compare)

        return {"on_hold":issues_on_hold,
               "on_hold_query":self.settings["query_onhold"],
               "unassigned":issues_in_q,
               "unassigned_query": self.settings["query_open"],
               "working":issues_working,
               "working_query": self.settings["query_working"],
                "illegal_query": self.settings["query_illegal"],
                "intake_total": issues_new_total,
                "intake_query": self.settings["query_intake"],
            }



