import datetime


class QanbanStats:

    ## Deze klasse houdt statistieken bij, zodat ik niet continue JIRA hoef te querien
    _dateformat = "%Y-%m-%d"

    @staticmethod
    def get_current_week():
        return datetime.datetime.now().isocalendar()[1]

    def __init__(self, jiraParser, config):
        self.jiraParser = jiraParser
        self.config = config
        self.resolved_num = config.getint("qanban","qanban_resolved_per_week")
        self.per_week_resolved = {}  ## Team / {} with {} resolved / week
        self.last_time_check = False



    def get_resolved_in_week(self, first_day_of_week, team):
        ## Eerst de bijbhorende resolved query samenstellen
        query = self.config.get("qanban_" + team, "query_resolved_base_query")
        query +=  "AND resolved >= "
        query += first_day_of_week.strftime("%Y-%m-%d")
        query += " AND resolved <= "
        query += (first_day_of_week + datetime.timedelta(days=7)).strftime(QanbanStats._dateformat)
        results = self.jiraParser.get_jira_total(query)
        return results


    def get_resolved_per_week(self, team):

        qnow = datetime.datetime.today().strftime(QanbanStats._dateformat)

        ## Invalidate cache if last check was not today
        if(self.last_time_check != qnow):
            self.last_time_check = qnow
            self.per_week_resolved = {}

        ## QUERY EVERYTHING!
        if team not in self.per_week_resolved:
            resolved_per_week = {}
            self.per_week_resolved[team] = resolved_per_week

        resolved_per_week = self.per_week_resolved[team]
        current_week_start = datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)
        current_week_start_str = current_week_start.strftime(QanbanStats._dateformat)

        results = []
        for i in range(0,self.resolved_num):
            if(current_week_start_str not in resolved_per_week):
                resolved_per_week[current_week_start_str] = self.get_resolved_in_week(current_week_start, team)
            results.append(resolved_per_week[current_week_start_str])
            current_week_start = current_week_start - datetime.timedelta(days=7)
            current_week_start_str = current_week_start.strftime(QanbanStats._dateformat)

        results.reverse()
        return results