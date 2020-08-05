from datetime import datetime, timedelta

import sys

logfile_location = '/var/log/stunnel/stunnelclient.log'
lastlog_hours_ok = 24
lastlog_hours_warning = 48

exitcode = 0
message = "OK: Got Studielink messages in the last " + str(lastlog_hours_ok) + " hours."

studelink_log = False
try:
    studelink_log = open(logfile_location,'rb')
except Exception as e:
    message = "CRITICAL: Could not read Studielink STUNNEL logfile!"
    exitcode = 2

if studelink_log:
    lines = studelink_log.readlines()
    if len(lines) > 0:
            last_line = lines[-1]
            last_log = datetime.strptime(last_line[:19], '%Y.%m.%d %H:%M:%S')
    else:
            message = "OK: Studielink STUNNEL logfile was empty, probably just started"

    if (last_log + timedelta(hours = lastlog_hours_warning) < datetime.now()):
        message = "CRITICAL: Got NO Studielink messages since " + str(last_log)
        exitcode = 2
    elif(last_log + timedelta(hours = lastlog_hours_ok) < datetime.now()):
        message = "WARNING: Got NO Studielink messages since " + str(last_log)

print(message)
sys.exit(0)