from ConfigParser import ConfigParser


## MarkO: Deze klasse heb ik er ingevouwen omdat de Python 2 configparser niet kon omgaan met de geneste groepen
## "extrapolatie". Met deze klasse kun je in een config .ini bestand ook verwijzen naar andere secties als volgt:
##  ${andere.sectie:option}
## Dollar teken is dus overstijgend!
import logging

class QfoonConfigParser(ConfigParser, object):
    def __init__(self):
        self.logger = logging.getLogger()
        super(QfoonConfigParser, self).__init__()

    def get(self, section, option ):
        result = super(QfoonConfigParser, self).get(section, option)
        index = result.find("${", 0)
        while(index > -1):
            self.logger.debug("Got a QFOON specific ConfigParser option at index " + str(index) + " in " + result)
            endindex = result.find("}", index)
            tuple = result[index + 2:endindex].split(":")
            innervalue =  super(QfoonConfigParser, self).get(tuple[0], tuple[1])
            self.logger.debug("Parsed this to " + innervalue)
            result = result[0:index] + innervalue + result[endindex + 1:]
            index = result.find("${", index + len(innervalue))

        return result