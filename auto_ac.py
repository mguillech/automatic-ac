# -*- coding: utf-8 -*-
__author__ = 'mguillech'

import os
import sys
import getopt
import shutil
import datetime
import json
import urllib

try:
    import requests
except ImportError:
    _error_and_exit("You need to install the Python-Requests library")

try:
    import yaml
except ImportError:
    _error_and_exit("You need to install the PyYAML library")

# Constants go here
API_URL = 'https://your_ac_api_url'
API_TOKEN = 'your_api_token'
CONF_FILE = os.path.join(os.path.expanduser('~'), '.auto_ac.rc')

def _error_and_exit(msg):
    print "\nERROR: %s" % msg
    sys.exit(1)

def print_usage():
    print 'Usage: %s [optional arguments]' % sys.argv[0]
    print '''Where optional arguments could be:

    -c [--autocommit]\tAuto commit changes to your ActiveCollab profile'
    -a [--autodate]\tAutomatically calculate the week the application should load the times to
    -h [--help]\tThis screen
    '''
    sys.exit(0)

def calculate_week(for_date):
    WEEK_START = for_date - datetime.timedelta(days=for_date.weekday()) # Monday
    WEEK_END = WEEK_START + datetime.timedelta(days=4) # Friday
    return WEEK_START, WEEK_END

def date_range(date_start, date_end):
    delta = (date_end - date_start).days
    for d in xrange(delta + 1):
        yield date_start + datetime.timedelta(days=d)

class _AC_Connector(object):
    def __init__(self, api_url, api_token, conf_file):
        self.api_url = api_url
        self.api_token = api_token
        self.conf_file = conf_file
        self.user_id = None
        self.configuration = None

    def __load_configuration(self):
        if not os.path.exists(self.conf_file):
            edit_conf = raw_input('Configuration file does not exist. Would you like to edit a new one? (Y/n) ')
            if edit_conf.lower() in ('y', 'yes', ''):
                # Attempt to copy over sample file
                try:
                    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_ac.rc.sample'),
                        self.conf_file)
                except (IOError, OSError):
                    pass
                print 'Attempting to launch file editor...'
                if os.uname()[0] == 'Linux':
                    os.system('gedit %s' % self.conf_file)
                else:
                    os.system('notepad %s' % self.conf_file)
            else:
                sys.exit(0)
        try:
            fd = open(self.conf_file)
        except Exception, exc:
            _error_and_exit('Couldn\'t read %s: %s' % (self.conf_file, exc))
        else:
            loaded_conf = yaml.load(fd)
            if not isinstance(loaded_conf, dict):
                _error_and_exit('Configuration is not valid! Please re-create the configuration file')
            self.configuration = loaded_conf

    def __make_request(self, params={}, data={}, headers={}, method='GET'):
        method_lower = method.lower()
        parms = {'token': self.api_token, 'format': 'json'}
        parms.update(params)
        try:
            requests_function = getattr(requests, method_lower)
        except AttributeError:
            _error_and_exit('Invalid method passed to function!')
        try:
            if method_lower == 'get':
                r = requests_function(self.api_url, params=parms, headers=headers)
            else:
                r = requests_function(self.api_url, params=parms, data=data, headers=headers)
        except requests.exceptions.ConnectionError:
            _error_and_exit('Cannot connect to your ActiveCollab service!')
        try:
            return json.loads(r.content)
        except ValueError:
            return []

    def __set_user_id(self):
        params = {'path_info': 'info'}
        remote_info = self.__make_request(params)
        try:
            self.user_id = int(urllib.unquote(remote_info['logged_user']).split('/')[-1])
        except ValueError:
            _error_and_exit('Could not get the ID of your user!')
        else:
            return self.user_id

    def __get_projects(self):
        params = {'path_info': 'projects'}
        remote_projects = self.__make_request(params)
        return remote_projects

    def __get_milestones(self, project_id):
        params = {'path_info': 'projects/%s/milestones' % project_id}
        remote_milestones = self.__make_request(params)
        return remote_milestones

    def __get_tickets(self, project_id, milestone_id):
        params = {'path_info': 'projects/%s/tickets' % project_id}
        remote_tickets = self.__make_request(params)
        tickets = [ ticket for ticket in remote_tickets if ticket['milestone_id'] == milestone_id]
        return tickets

    def __get_times(self, project_id):
        params = {'path_info': 'projects/%s/time' % project_id}
        remote_times = self.__make_request(params)
        return remote_times

    def __add_time_record(self, project_id, ticket_id, description, record_date, time):
        params={'path_info': 'projects/%s/time/add' % project_id}
        data={'submitted': 'submitted', 'time[user_id]': self.user_id, 'time[value]': time,
              'time[record_date]': record_date, 'time[body]': description, 'time[billable_status]': 1,
              'time[parent_id]': ticket_id}
        # print params, data
        add_record = self.__make_request(params, data, method='POST')
        if 'id' not in add_record:
            print 'Error creating time record: %s' % add_record['field_errors']


def main(api_url, api_token, conf_file):
    # Internal flags
    AUTO_DATE = COMMIT = DATE = False

    try:
        opts, _ = getopt.getopt(sys.argv[1:], 'ach', ['autodate', 'commit', 'help'])
    except getopt.GetoptError, exc:
        print 'getopt error: %s\n' % exc
        print_usage()
    for o, a in opts:
        if o in ('-a', '--autodate'):
            AUTO_DATE = True
            DATE = datetime.date.today()
        elif o in ('-c', '--commit'):
            COMMIT = True
        elif o in ('-h', '--help'):
            print_usage()

    if not COMMIT:
        print 'WARNING! Time records will not be commited onto the ActiveCollab server (commit option is disabled)'

    if not DATE:
        try:
            date_input = raw_input('Please enter any date within the week you want to load times to (DD-MM-YYYY): ')
        except KeyboardInterrupt:
            _error_and_exit('Cancelled by user')
        if not date_input:
            _error_and_exit('No date specified, bailing out...')
        try:
            DATE = datetime.datetime.strptime(date_input, '%d-%m-%Y').date()
        except ValueError:
            _error_and_exit('Provided value didn\'t match the DD-MM-YYYY format')

    week_start, week_end = calculate_week(DATE)
    # Initialize ActiveCollab connector with personal configuration
    connector = _AC_Connector(api_url, api_token, conf_file)
    connector.__load_configuration()
    connector.__set_user_id()

    print 'Attempting to load time data starting at %s and up to %s ...' % (week_start, week_end)

    remote_projects = connector.__get_projects()
    if not remote_projects:
        _error_and_exit('No remote projects are viewable by you')
    for project_name, project_milestones in connector.configuration.items():
        matched_projects = [ _ for _ in remote_projects if project_name.lower() in _['name'].lower() ]
        if not matched_projects:
            continue
        # print matched_projects
        for matched_project in matched_projects:
            remote_times = connector.__get_times(matched_project['id'])
            remote_milestones = connector.__get_milestones(matched_project['id'])
            for record_date in date_range(week_start, week_end):
                if [ _ for _ in remote_times if str(record_date) in _['record_date']
                        and _['user']['id'] == connector.user_id ]:
                    print 'Skipping time records for date %s (something loaded)...' % record_date
                    continue
                for milestone_name, milestone_tickets in project_milestones.items():
                    matched_milestones = [ _ for _ in remote_milestones if milestone_name.lower() in _['name'].lower() ]
                    if not matched_milestones or not milestone_tickets:
                        continue
                    # print matched_milestones
                    for matched_milestone in matched_milestones:
                        remote_tickets = connector.__get_tickets(matched_project['id'], matched_milestone['id'])
                        for ticket_name, ticket_time in milestone_tickets.items():
                            matched_tickets = [ _ for _ in remote_tickets
                                                if ticket_name.lower() in _['name'].lower() ]
                            if not matched_tickets:
                                continue
                            # print matched_tickets
                            if COMMIT:
                                for matched_ticket in matched_tickets:
                                    ticket_description = matched_ticket['name']
                                    print 'Adding time record for date %s, ticket ID %d...' % (record_date,
                                                                                        matched_ticket['ticket_id'])
                                    connector.__add_time_record(matched_project['id'],
                                        matched_ticket['ticket_id'], ticket_description, str(record_date),
                                        ticket_time)

if __name__ == '__main__':
    main(API_URL, API_TOKEN, CONF_FILE)
