#!/usr/bin/python
import ConfigParser
import logging
import netifaces
import operator
import re
import socket
import sys
import traceback
from os import listdir
from os.path import isfile, join

import flask

from flask import request
from flask import send_file

from classes.JIRA import JiraParser, JiraQueryException
from classes.PhoneParser import PhoneParser
from classes.QanbanScrubber import QanbanScrubber
from classes.QanbanStats import QanbanStats
from classes.QfoonConfigParser import QfoonConfigParser
from classes.RFCConverter import RFCConverter
from classes.SMSNotifier import SMSNotifier

app = flask.Flask(__name__)

# MarkO: Script gooit een webserver op op 0.0.0.0:5000
#
# Installatie:
#  - Installeer Python 2.7.0 (geen python 3 want mechanize is er nog niet voor p3)
#  - apt-get install python-dev python-pip
#  - pip install mechanize flask python-dateutil pytz netifaces
#  - instlaleer thawte root CA in browser
#  - python qfoon.py
#
#

configfile = "qfoon.ini"
config = QfoonConfigParser()

try:
    config.read(configfile)
except Exception as e:
    print("Could not read " + configfile)
    print(e)
    sys.exit()


debug = config.getboolean("other", "debug")

logger = logging.getLogger()

handler = logging.StreamHandler()
logger.addHandler(handler)

## Disable access logging
log = logging.getLogger('werkzeug')
if(not debug):
    log.setLevel(logging.ERROR)
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.DEBUG)

templatedir = "./word_templates/"
savedir = "./word_results"


def split_and_strip(unsplit_string):
    return [x.strip() for x in unsplit_string.split(",")]

def get_my_ip():
    try:
        ip = netifaces.ifaddresses('wlan0')[2][0]['addr']
    except:
        ip = socket.gethostbyname(socket.gethostname())
    return ip

@app.route('/rest/qanban/<team>')
def flask_route_qanban_json(team):
    try:
        team_config = dict(config.items("qanban_" + team))
        team_config = {key: config.get("qanban_" + team, key) for key in team_config.keys()}
        qbs = QanbanScrubber(team_config, jiraParser)
        result = qbs.qanban_scrub()
        result["resolved_stats"] = qbstats.get_resolved_per_week(team)
    except JiraQueryException as e:
        result = {"qanbanerror": "JIRA query problem", "message": e.message}
    except ConfigParser.NoSectionError as e:
        result = {"qanbanerror":"No such team", "message": e.message}
    return flask.jsonify(result)


@app.route('/qanban/<team>')
@app.route('/qanban/<team>/<page>')
def flask_route_qanban(team,page="qanban.html"):
    jiraurl = config.get("JIRA", "url")
    try:
        title = "Qualogy for Support - " + config.get("qanban_" + team, "screenname")
    except ConfigParser.NoOptionError as e:
        title = "(Configure this team first)"
    return flask.render_template(page, ip=get_my_ip(), clientip=request.remote_addr, team=team, jiraurl=jiraurl, title=title)

@app.route("/refresh")
def refresh():
    phoneParser.refresh()
    return flask.redirect('/')

@app.route("/phones")
def flask_current_phones():
    numbers = phoneParser.get_current_phones()
    return flask.jsonify(numbers)

@app.route("/setphone/<group>/<number>")
def flask_set_phone(group,number):
    if phoneParser.set_number(group, number):
        phoneParser.refresh()
        return flask.jsonify({"result": "ok"})
    else:
        return flask.jsonify({"result": "error"})

@app.route("/jtorfc")
def flask_jtorfc():
    templates = [f for f in listdir(templatedir) if isfile(join(templatedir, f)) and f.find("docx") > -1]
    return flask.render_template('rfctoj.html', ip=get_my_ip(), clientip=request.remote_addr,templates=templates)

@app.route('/rest/jira/<ticket>')
def flask_jira_check_if_issue_exists(ticket):
    return flask.jsonify({"exists": jiraParser.get_ticket_exists(ticket)})

# http://127.0.0.1:5000/rest/Request%20for%20Change%20Template%20JIRA.docx/ASB-7813
@app.route('/rest/jira/word/<template>/<ticket>')
def flask_jira_to_template(template, ticket):
    info =  jiraParser.get_ticket_info(ticket.upper())
    templatefile = templatedir + "/" + template
    try:
        rfcconv = RFCConverter(templatefile,savedir)
        rfcname, rfcobject = rfcconv.convert(info)
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return "Got an error while parsing: " + str(e)
    else:
        return send_file(rfcobject,
                         attachment_filename=rfcname,
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                         as_attachment=True, cache_timeout=0)

@app.route("/jiraraw")
def flask_current_raw_jira():
    ## JIRA issues opzoeken
    data = jiraParser.get_unassigned()
    return flask.jsonify(data)

@app.route("/jira_image/<path:query>")
def flask_jira_icon(query):
    image= jiraParser.get_jira_image(query, flask.request.query_string)
    if(image[:5] == "<?xml"):
        response = flask.make_response(image)
        response.headers['Content-Type'] = "image/svg+xml"
    else:
        response = flask.make_response(image)
    return response

## Pages should be comma seperaterd
@app.route("/rotater/<pages>/<time>")
def flask_rotater(pages, time):
    return flask.render_template('framerotater.html', pages=pages, time=time)

@app.route("/notifier/<role>/<sender>", methods=["POST"])
def flask_send_sms(role, sender):
    if notifier.accept_role(role):
        bodycontent = request.json
        if(notifier.send_message(bodycontent["message"], sender, role)):
            return flask.jsonify({"result": "ok"})
        else:
            return flask.jsonify({"result": "error", "error":"Message duplicate, try again later"})
    else:
        return flask.jsonify({"result": "error", "error":"Role not accepted"})


@app.route("/jira/<queryname>")
@app.route("/jira")
def flask_current_jira(queryname = False ):
    # JIRA issues opzoeken
    if not queryname:
        ## This is pure business logic, this should not be here. Sorry!
        unassignedquery = config.get("JIRA", "unassignedquery")
    else:
        unassignedquery = config.get("JIRA", queryname)

    statescreensize = config.getint("JIRA", "statescreensize")
        ## Attend! Tijdelijk, moet er weer uit!
    if queryname == "unassignedqueryqcar":
        statescreensize += 5

    error = False
    try:
        data = jiraParser.get_jira_data(unassignedquery + "&fields=key,summary,created,project,priority,parent&maxResults=" + str(statescreensize))
    except JiraQueryException as e:
        error = {"qanbanerror": "JIRA query problem", "message": e.message}

    if not error:
        datatableIssues = []
        if "issues" in data:
            for issue in data["issues"]:
                selectedfields = [ issue["fields"]["project"]["avatarUrls"]["48x48"],
                                         issue["fields"]["priority"]["iconUrl"],
                                         issue["key"],
                                         issue["fields"]["summary"],
                                         issue["fields"]["created"],
                                         issue['team'],
                                         issue['recent']]
                selectedfields.append(issue["fields"]["parent"]["key"] if "parent" in issue["fields"] else False)
                datatableIssues.append(selectedfields)
        result = {"data":datatableIssues}
    else:
        result = error
    return flask.jsonify(result)

@app.route("/jiratotal")
def flask_total_jira():
    # JIRA issues opzoeken
    unassignedquery = config.get("JIRA", "unassignedquery")
    total = jiraParser.get_jira_total(unassignedquery)
    return flask.jsonify({"total":total})

@app.route("/jiraopentotal")
def flask_total_open_jira():
    openquery = config.get("JIRA", "openquery")
    total = jiraParser.get_jira_total(openquery)
    return flask.jsonify({"total" : total})


@app.route("/pager")
def flask_pager():
    ## Dit is wat gekopieerde logica uit de phone parser. Als schiphol lang blijft moeten we dit aanpassen
    le_dict = {}
    for pair in config.items("phonenumbers"):
        ## Bug fix voor issue met DEFAULT section die wordt meegenomen hier
        if re.match("^[0-9]+$", pair[0]):
            le_dict[pair[0]] = pair[1]
    sorted_phonedict = sorted(le_dict.items(), key=operator.itemgetter(1))
    return flask.render_template('pager.html', ip=get_my_ip(), clientip=request.remote_addr, numbersdict=sorted_phonedict)


@app.route("/phone")
def flask_phone():
    ## Dit is wat gekopieerde logica uit de phone parser. Als schiphol lang blijft moeten we dit aanpassen
    le_dict = {}
    for pair in config.items("phonenumbers"):
        ## Bug fix voor issue met DEFAULT section die wordt meegenomen hier
        if re.match("^[0-9]+$", pair[0]):
            le_dict[pair[0]] = pair[1]
    sorted_phonedict = sorted(le_dict.items(), key=operator.itemgetter(1))
    return flask.render_template('phone.html', ip=get_my_ip(), clientip=request.remote_addr, groups=phoneParser.forwarding_groups + phoneParser.hunt_groups, numbersdict=sorted_phonedict)

@app.route("/pager/set/<number>")
def flask_pager_set(number):
    phoneParser.setPager(number)
    phoneParser.refresh()
    return flask.jsonify({"pager_number" : number})

@app.route("/pager/get")
def flask_pager_get():
    number = phoneParser.getCurrentPager()
    return flask.jsonify({"pager_number" : number})


@app.route("/schiphol")
def flask_schiphol():
    ## Dit is wat gekopieerde logica uit de phone parser. Als schiphol lang blijft moeten we dit aanpassen
    schipholdict = {}
    for pair in config.items("phonenumbers_schiphol"):
        ## Bug fix voor issue met DEFAULT section die wordt meegenomen hier
        if re.match("^[0-9]+$", pair[0]):
            schipholdict[pair[0]] = pair[1]
    sorted_phonedict = sorted(schipholdict.items(), key=operator.itemgetter(1))
    return flask.render_template('schiphol.html', ip=get_my_ip(), clientip=request.remote_addr, groups=phoneParser.forwarding_groups + phoneParser.hunt_groups, numbersdict=sorted_phonedict, groupname='standby-schiphol')


@app.route("/qcar")
def hello_qcar():
    return flask.render_template('qforstate_qcar.html', ip=get_my_ip(), clientip=request.remote_addr, jiraurl=config.get("JIRA", "url"))

@app.route("/settings")
def flask_show_settings():
    file = open("./qfoon.ini" , "r")
    result = file.readlines()
    file.close()
    stripped = [line.strip().split(":",1) for line in result]
    return flask.render_template('qfoon_settings.html', ip=get_my_ip(), clientip=request.remote_addr,
                                 ini=stripped)



@app.route("/")
def hello():
    return flask.render_template('qforstate.html', ip=get_my_ip(), clientip=request.remote_addr, jiraurl=config.get("JIRA", "url"), ledserverip = config.get("JIRA", "ledserverip"))

print("Running.. Logger is at level " + str(logger.getEffectiveLevel()) + " (ERROR is level 40)")
phoneParser = PhoneParser(config)
notifier = SMSNotifier(config.items("SMSNotification"),phoneParser)

teamDict = {}
allOperators = set(split_and_strip(config.get("JIRA", "operatorlist")))

## Ik haal de projecten mapping uit de team configuraties en alle leden
for section in config.sections():
    if config.has_option(section, "projects"):
        projects = split_and_strip(config.get(section, "projects"))
        team = config.get(section, "team")
        for project in projects:
            teamDict[project] = team

jiraParser = JiraParser(baseurl=config.get("JIRA", "url"),
                        username=config.get("JIRA", "user"),
                        password=config.get("JIRA", "password"),
                        teamdict=teamDict,
                        recent=config.getint("JIRA", "newtime")
                        )
qbstats = QanbanStats(jiraParser, config)

host = config.get("other", "listenaddr")
port = config.getint("other", "listenport")
logger.info("Now starting webserver at " + host + ":" + str(port) + ", debug is " + str(debug))

if __name__ == "__main__":

    app.run(host=host,
            port=port,
            debug=False,
            threaded=True)

