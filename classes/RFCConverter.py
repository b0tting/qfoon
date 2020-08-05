import os

import datetime
from StringIO import StringIO
from io import BytesIO

from docxtpl import DocxTemplate, R

"""

Install lxml from http://www.lfd.uci.edu/~gohlke/pythonlibs/#lxml for your python version. It's a precompiled WHL with required modules/dependencies.

The site lists several packages, when e.g. using Win32 Python 2.7, use lxml-3.6.1-cp27-cp27m-win32.whl.

Download the file, and then install with

pip install C:\path\to\downloaded\file\lxml-3.6.1-cp27-cp27m-win32.whl


"""

class RFCConverter():
    def __init__(self, templatefile, targetlocation="./"):
        if not os.path.isfile(templatefile):
            raise Exception("Could not find template file " + templatefile)
        if not os.path.isdir(targetlocation):
            raise Exception("Could not find save location " + targetlocation)

        self.templatefile = templatefile
        self.targetlocation = targetlocation

    @staticmethod
    def cleandate(uncleandate=False):
        # 2016-12-16T10:25:03.000+0100
        if uncleandate:
            if len(uncleandate) == 10:
                dateobj = datetime.datetime.strptime(uncleandate[:19], "%Y-%m-%d")
            else:
                dateobj = datetime.datetime.strptime(uncleandate[:19], "%Y-%m-%dT%H:%M:%S")
        else:
            dateobj = datetime.datetime.now()
        return dateobj.strftime("%d %b %Y")




    def convert(self, jira_json):
        doc = DocxTemplate(self.templatefile)

        context = {}
        context["ticketnumber"] = jira_json["key"]
        context["priority"] = jira_json["fields"]["priority"]["name"]
        context["pref_resolution_date"] = RFCConverter.cleandate(jira_json["fields"]["duedate"])
        context["createdate"] = RFCConverter.cleandate(jira_json["fields"]["created"])
        context["submitter"] = jira_json["fields"]["creator"]["displayName"]
        context["components"] = ", ".join([x["name"] for x in jira_json["fields"]["components"]])
        context["submittermail"] = jira_json["fields"]["creator"]["emailAddress"]
        context["description"] = R(jira_json["fields"]["description"])
        context["accepted_by"] = jira_json["fields"]["creator"]["displayName"]
        context["print_date"] = RFCConverter.cleandate()
        context["verified_by"] = jira_json["fields"]["creator"]["displayName"]
        context["change_number"] = jira_json["key"]
        doc.render(context)

        target = StringIO()
        doc.save(target)
        target.seek(0)

        name = "RFC_" + jira_json["key"] + ".docx"
        return name, target
        # Map jira_json to target fields

