#!/usr/bin/python
import traceback
import urllib2
import re
import urllib
import os
import datetime
import json
import mechanize
import operator


class PhoneParser:
    PAGER_FILE = "pager.txt"
    expressioninit = "TelephoneContext=([\w-]+)"

    ## Voeg user toe voor uitvragen!
    expressionuser = "TelephoneContext=([\w_-]+)&amp;[\w=\"\&;\%\.>\s]+"
    expressionfwd = "TelephoneUserSettingsCallForwarding\?TelephoneContext=([\w_-]+)&"
    phonesearcher = re.compile("name=\"CallForwardingNoAnswerNumber\" type=\"text\" value=\"([\w-]*)\"", re.MULTILINE)
    forwardphonesearcher = re.compile("name=\"CallForwardingNoAnswer\" type=\"checkbox\" value=\"(true|false)\"", re.MULTILINE)

    hgphoneexpression = re.compile("name=\"ForwardToPhoneNumber\" type=\"text\" value=\"([\w-]*)\"")
    verifyexpression = "name=\"__RequestVerificationToken\" type=\"hidden\" value=\"([\w-]+)"

    savesuccesexpression = re.compile('<div class="alert alert-success">... Opgeslagen<\/div>')


    phoneurl1 = "/Telephone/TelephoneUserSettingsCallForwarding"
    phone1url1 = "/TelephoneExchange/TelephoneExchangeMainTabs"
    phone2url1 = "/TelephoneExchange/Users"
    phone3url1 = "/Telephone/TelephoneUserSettings"
    phone4url1 = "/Telephone/TelephoneUserSettingsCallForwarding"
    phone4url1_2 = "/Telephone/SaveTelephoneUserSettingsCallForwarding"
    phone5url1 = "/TelephoneExchange/HuntGroupList"
    phone6url1 = "/TelephoneExchange/HuntGroup"
    phone7url1 = "/TelephoneExchange/HuntGroupCallForwardingAdvanced"



    def __init__(self, config):
        self.debug = config.getboolean("other", "debug")

        self.user = config.get("billing", "user")
        self.password = config.get("billing", "password")
        self.voipurl=config.get("billing", "voipurl")
        self.customerid=config.get("billing", "customerid")

        self.lastcheck = "./lastcheck.txt"

        self.phone_minutes_between=config.getint("other", "phonerefreshtime")

        # Alle telefoonnummers van consultants
        self.phoneDict = {}
        for pair in config.items("phonenumbers"):
            ## Bug fix voor issue met DEFAULT section die wordt meegenomen hier
            if re.match("^[0-9]+$", pair[0]):
                self.phoneDict[pair[0]] = pair[1]
        for pair in config.items("phonenumbers_schiphol"):
            ## Bug fix voor issue met DEFAULT section die wordt meegenomen hier
            if re.match("^[0-9]+$", pair[0]):
                self.phoneDict[pair[0]] = pair[1]



        self.loginurl = self.voipurl + "Account/LogOn?ReturnUrl=%2f"
        self.baseurl = self.voipurl + "Customer"

        self.huntgroupexpression = "\/Customer\/TelephoneExchange\/HuntGroupList\?ContextCustomerId="+self.customerid+"&TelephoneContext=([\w-]+)"
        self.huntgrouplistexpression = "([\w-]+)\">\s+"
        self.hgadvancedexpression = "\/Customer\/TelephoneExchange\/HuntGroupCallForwardingAdvanced\?ContextCustomerId="+self.customerid+"&TelephoneContext=([\w-]+)"
        self.timeoutforwardphonesearcher = re.compile("name=\"ForwardAfterTimeout\" type=\"checkbox\" value=\"(true|false)\"", re.MULTILINE)

        self.forwarding_groups = [e.strip() for e in config.get('phonegroups', 'forwarding').split(',')]
        self.hunt_groups = [e.strip() for e in config.get('phonegroups', 'huntgroups').split(',')]


    @classmethod
    def get_phone_context(cls,raw, expression):
        tcontext = False
        context = re.search(expression, raw)
        if context:
            tcontext = context.group(1)
        return tcontext

    @classmethod
    def get_verify_token(cls,raw):
        tcontext = False
        context = re.search(PhoneParser.verifyexpression, raw)
        if context:
            tcontext = context.group(1)
        return tcontext


    def get_next_URI(self,nexturl, browser, formerresultexpression=False, ignoreToken=False, context=False, postdata=False):
        nexturl = self.baseurl + nexturl + "?ContextCustomerId=" + self.customerid + "&"
        raw = browser.response().read()
        if not context:
            context = PhoneParser.get_phone_context(raw, formerresultexpression)

        if not context:
            if self.debug:
                print("looking for " + str(formerresultexpression))
                print(raw)
            raise Exception("Could not find a context in response")

        token = PhoneParser.get_verify_token(raw)
        if token and not ignoreToken:
            tokenset = {"__RequestVerificationToken": token}
            if postdata:
                tokenset.update(postdata)
            tokendata = urllib.urlencode(tokenset)
        else:
            tokendata = None

        newurl = nexturl + "TelephoneContext=" + context

        if self.debug:
            print(newurl)
            print(tokendata)

        try:
            browser.open(newurl, tokendata)
        except urllib2.URLError as e:
            print("URL error. Could not connect to: " + newurl)
            traceback.print_exc()


    def normalize_number(self,number):
        number = (str(number)).replace(" ", "").replace("-", "")
        if number in self.phoneDict.keys():
            return self.phoneDict[number]
        elif number:
            return number
        else:
            return None

    def get_current_phones(self):
        # Even checken wanneer de laatste foon update was
        if not os.path.isfile(self.lastcheck) or (datetime.datetime.fromtimestamp(os.path.getmtime(self.lastcheck)) < (
                    datetime.datetime.now() - datetime.timedelta(minutes=self.phone_minutes_between))):
            numbers = self.get_current()
            f = open(self.lastcheck, 'w')
            f.write(json.dumps(numbers))
            f.close()
        else:
            f = open(self.lastcheck, 'r')
            numbers = json.loads(f.read())
        return numbers

    def get_forwarded_number(self,browser, userinitcontext, forwardgroup):
        # Klik weer op gebruikers
        self.get_next_URI(PhoneParser.phone2url1, browser, context=userinitcontext, ignoreToken=True)

        # Klik op qfors APPS
        self.get_next_URI(PhoneParser.phone3url1, browser, PhoneParser.expressionuser + forwardgroup)

        # Klik op doorschakelen. Voorkom doorsturen van het security token om een HTTP 500 te voorkomen
        self.get_next_URI(PhoneParser.phone4url1, browser, PhoneParser.expressionfwd, True)

        # Peuter de huidige doorschakeling tevoorschijn
        raw = browser.response().read()
        if self.forwardphonesearcher.search(raw).group(1) == "true":
            phone = self.phonesearcher.search(raw).group(1)
        else:
            phone = None
        return phone


    def set_forwarded_number(self,browser, userinitcontext, forwardgroup, newnumber):
        # Klik weer op gebruikers
        self.get_next_URI(PhoneParser.phone2url1, browser, context=userinitcontext, ignoreToken=True)

        # Klik op qfors APPS
        self.get_next_URI(PhoneParser.phone3url1, browser, PhoneParser.expressionuser + forwardgroup)

        # Klik op doorschakelen. Voorkom doorsturen van het security token om een HTTP 500 te voorkomen


        post_vars = {"CallForwardingDirectEnabledChanged":"False",
            "CallForwardingDirectNumberChanged":"False",
            "CallForwardingBusyEnabledChanged":"False",
            "CallForwardingBusyNumberChanged":"False",
            "CallForwardingNoAnswerChanged":"True",
            "CallForwardingNoAnswer":"True",
            "CallForwardingNoAnswerNumberChanged":"True",
            "CallForwardingNoAnswerNumberVisible":"True",
            "CallForwardingNoAnswerNumber":newnumber,
            "CallForwardingNoAnswerNrRingsChanged":"True",
            "CallForwardingNoAnswerNrRingsVisible":"True",
            "CallForwardingNoAnswerNrRings":"4",
            "CallForwardingNotReachableChanged":"False",
            "CallForwardingNotReachableNumberChanged":"False"}

        self.get_next_URI(PhoneParser.phone4url1_2, browser, PhoneParser.expressionfwd, postdata=post_vars)

        raw = browser.response().read()
        result = self.savesuccesexpression.search(raw)
        return result is not None

    def set_huntgroup_number(self,browser, huntgroupcontext, huntgroup, newnumber):
        # Nu op zoek naar de FMW standby foon
        # Belgroep klikken
        self.get_next_URI(PhoneParser.phone5url1, browser, context=huntgroupcontext, ignoreToken=True)

        # Fusion klikken
        self.get_next_URI(PhoneParser.phone6url1, browser, self.huntgrouplistexpression + huntgroup, True)

        post_vars = {"AllowCallWaitingForAgents":False,
        "HuntAfterNoAnswer":False,
        "NoAnswerNumberOfRings":5,
        "ForwardAfterTimeout":True,
        "ForwardTimeoutSeconds":3,
        "ForwardToPhoneNumber":newnumber,
        "EnableNotReachableForwarding":False,
         "NotReachableForwardToPhoneNumber":"",
         "SetBusyWhenNotReachable":False}

        self.get_next_URI(PhoneParser.phone7url1, browser, self.hgadvancedexpression, postdata=post_vars)

        raw = browser.response().read()
        result = self.savesuccesexpression.search(raw)
        return result is not None

    def get_huntgroup_number(self,browser, huntgroupcontext, huntgroup):
        # Nu op zoek naar de FMW standby foon
        # Belgroep klikken
        self.get_next_URI(PhoneParser.phone5url1, browser, context=huntgroupcontext, ignoreToken=True)

        # Fusion klikken
        self.get_next_URI(PhoneParser.phone6url1, browser, self.huntgrouplistexpression + huntgroup, True)

        # Advanced klikken
        self.get_next_URI(PhoneParser.phone7url1, browser, self.hgadvancedexpression, True)

        raw = browser.response().read()
        if self.timeoutforwardphonesearcher.search(raw).group(1) == "true":
            phone = self.hgphoneexpression.search(raw).group(1)
        else:
            phone = None
        return phone

    def init_browser_object(self):
        browser = mechanize.Browser()
        browser.set_handle_equiv(True)
        browser.set_handle_gzip(True)
        browser.set_handle_redirect(True)
        browser.set_handle_referer(True)
        browser.set_handle_robots(False)

        # Ik gebruik mechanize voor zijn cookie jar
        cj = mechanize.CookieJar()
        browser.set_cookiejar(cj)
        browser.open(self.loginurl)
        browser.select_form(nr=0)
        browser.form['UserName'] = self.user
        browser.form['Password'] = self.password
        browser.submit()

        return browser

    def set_number(self,group, number):
        browser = self.init_browser_object()

        # Telefoonapp gebruikt "context" variabelen om aan te geven in welke context de client zich bevind
        # en waar hij naar toe gaat. Die moeten we dus uit iedere response slopen voordat we een volgend
        # verzoek sturen.

        # Open main tab, aangeschopt door de loginform
        self.get_next_URI(PhoneParser.phone1url1, browser, PhoneParser.expressioninit)
        huntgrouptab = PhoneParser.get_phone_context(browser.response().read(), self.huntgroupexpression)
        if group in self.forwarding_groups:
            raw = browser.response().read()
            searcher = re.compile(self.expressioninit, re.MULTILINE)
            userinit = searcher.search(raw).group(1)
            result = self.set_forwarded_number(browser,userinit, group, number)
        else:
            result = self.set_huntgroup_number(browser,huntgrouptab, group, number)
        return result


    def get_current(self):
        results = {}
        browser = self.init_browser_object()

        # Telefoonapp gebruikt "context" variabelen om aan te geven in welke context de client zich bevind
        # en waar hij naar toe gaat. Die moeten we dus uit iedere response slopen voordat we een volgend
        # verzoek sturen.

        # Open main tab, aangeschopt door de loginform
        self.get_next_URI(PhoneParser.phone1url1, browser, PhoneParser.expressioninit)

        huntgrouptab = PhoneParser.get_phone_context(browser.response().read(), self.huntgroupexpression)

        # Klik op gebruikers
        raw = browser.response().read()
        searcher = re.compile(self.expressioninit, re.MULTILINE)
        userinit = searcher.search(raw).group(1)
        for forward in self.forwarding_groups:
            forwarded = self.get_forwarded_number(browser, userinit, forward)
            results[forward] = [self.normalize_number(forwarded), forwarded]

        for huntgroup in self.hunt_groups:
            hunted = self.get_huntgroup_number(browser, huntgrouptab, huntgroup)
            results[huntgroup] = [self.normalize_number(hunted), hunted]

        results["pager_duty"] = [self.normalize_number(self.getCurrentPager()), self.getCurrentPager()]

        return results

    def get_ordered_phonedict(self):
        sorted_phonedict= sorted(self.phoneDict.items(), key=operator.itemgetter(1))
        return sorted_phonedict

    def refresh(self):
        if os.path.isfile(self.lastcheck):
            os.remove(self.lastcheck)


    def setPager(self, number):
        text_file = open(PhoneParser.PAGER_FILE, "w")
        text_file.write(number)
        text_file.close()

    def getCurrentPager(self):
        number = "error"
        try:
            text_file = open(PhoneParser.PAGER_FILE, "r")
            number = text_file.read().replace('\n', '')
            text_file.close()
        except Exception, e:
            pass
        return number
