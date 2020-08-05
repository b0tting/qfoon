import logging
import messagebird
import time


class SMSNotifier:

    def __init__(self, config, phoneParser):
        configDict = dict(config)
        self.apikey = configDict["apikey"]
        self.notifier = configDict["notifier"]
        self.duplicatetime = configDict["duplicatetime"]
        ## References the hunt groups found in the VOIP site
        self.roles = configDict["roles"].split(",")
        self.phoneParser = phoneParser
        self.lastmessages = {}

    def accept_role(self, role):
        return role in self.roles

    def is_recent_duplicate(self, message):
        returnval = message in self.lastmessages
        self.lastmessages[message] = time.time()
        return returnval

    def clean_last_messages(self):
        now = time.time()
        ## ook nog: schoon oude shit op
        delete = []
        for key, value in self.lastmessages.iteritems():
            if((now - value) > self.duplicatetime):
                delete.append(key)
        for key in delete:
            self.lastmessages.pop(key)

    def send_message(self, message, sender, role):
        self.clean_last_messages()
        returnval = True
        message = sender + ": " + message
        if(not self.is_recent_duplicate(message)):
            client = messagebird.Client(self.apikey)
            phones = self.phoneParser.get_current_phones()
            phonenumber = phones[role]

            ## FETCH ROLE INFO
            msg = client.message_create(self.notifier, phonenumber, message)
            logging.info("Will not send duplicate message received from " + sender + ": " + message)
            logging.debug(self.debug_message(msg))
        else:
            returnval = False
            logging.warning("Will not send duplicate message received from " + sender +  ": " + message )
        return returnval

    def debug_message(self, msg):
        # Print the object information.
        debugmsg = 'The following information was returned as a Message object:\n'
        debugmsg += '  id                : ' + str(msg.id) + '\n'
        debugmsg += '  href              : '+str(msg.href) + '\n'
        debugmsg += '   direction         : '+str(msg.direction) + '\n'
        debugmsg += '   type              : '+str(msg.type) + '\n'
        debugmsg += '   originator        : '+str(msg.originator) + '\n'
        debugmsg += '   body              : '+str(msg.body) + '\n'
        debugmsg += '   reference         : '+str(msg.reference) + '\n'
        debugmsg += '   validity          : '+str(msg.validity) + '\n'
        debugmsg += '   gateway           : '+str(msg.gateway) + '\n'
        debugmsg += '   typeDetails       : '+str(msg.typeDetails) + '\n'
        debugmsg += '   datacoding        : '+str(msg.datacoding) + '\n'
        debugmsg += '   mclass            : '+str(msg.mclass) + '\n'
        debugmsg += '   scheduledDatetime : '+str(msg.scheduledDatetime) + '\n'
        debugmsg += '   createdDatetime   : '+str(msg.createdDatetime) + '\n'
        debugmsg += '  recipients        : \n' + str(msg.recipients) + '\n'



