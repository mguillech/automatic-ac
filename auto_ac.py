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
    print "ERROR: %s" % msg
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

def load_configuration(CONF_FILE):
    if not os.path.exists(CONF_FILE):
        edit_conf = raw_input('Configuration file does not exist. Would you like to edit a new one? (Y/n) ')
        if edit_conf.lower() in ('y', 'yes', ''):
            # Attempt to copy over sample file
            try:
                shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_ac.rc.sample'), CONF_FILE)
            except (IOError, OSError):
                pass
            print 'Attempting to launch file editor...'
            if os.uname()[0] == 'Linux':
                os.system('gedit %s' % CONF_FILE)
            else:
                os.system('notepad %s' % CONF_FILE)
        else:
            sys.exit(0)
    try:
        fd = open(CONF_FILE)
    except Exception, exc:
        _error_and_exit('Couldn\'t read %s: %s' % (CONF_FILE, exc))
    else:
        loaded_conf = yaml.load(fd)
        if not isinstance(loaded_conf, dict):
            _error_and_exit('Configuration is not valid! Please re-create the configuration file')
        return loaded_conf

def _make_request(token, url, params={}, data={}, headers={}, method='GET'):
    method_lower = method.lower()
    parms = {'token': token, 'format': 'json'}
    parms.update(params)
    try:
        requests_function = getattr(requests, method_lower)
    except AttributeError:
        _error_and_exit('Invalid method passed to function!')
    if method_lower == 'get':
        r = requests_function(url, params=parms, headers=headers)
    else:
        r = requests_function(url, params=parms, data=data, headers=headers)
    try:
        return json.loads(r.content)
    except ValueError:
        return []

def _get_user_id(token, url):
    params = {'path_info': 'info'}
    remote_info = _make_request(token, url, params)
    try:
        return int(urllib.unquote(remote_info['logged_user']).split('/')[-1])
    except ValueError:
        _error_and_exit('Could not get the ID of your user!')

def _get_projects(token, url):
    params = {'path_info': 'projects'}
    remote_projects = _make_request(token, url, params)
    return remote_projects

def _get_milestones(token, url, project_id):
    params = {'path_info': 'projects/%s/milestones' % project_id}
    remote_milestones = _make_request(token, url, params)
    return remote_milestones

def _get_tickets(token, url, project_id, milestone_id):
    params = {'path_info': 'projects/%s/tickets' % project_id}
    remote_tickets = _make_request(token, url, params)
    tickets = [ ticket for ticket in remote_tickets if ticket['milestone_id'] == milestone_id]
    return tickets

def _add_time_record(token, url, user_id, project_id, ticket_id, description, record_date, time):
    params={'path_info': 'projects/%s/time/add' % project_id}
    data={'submitted': 'submitted', 'time[user_id]': user_id, 'time[value]': time, 'time[record_date]': record_date,
          'time[body]': description, 'time[billable_status]': 1, 'time[parent_id]': ticket_id}
    print params, data
    # add_record = _make_request(token, url, params, data, method='POST')
    # if 'id' not in add_record:
    #     print 'Error creating time record: %s' % add_record['field_errors']


def main(token, url, conf):
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
        date_input = raw_input('Please enter any date within the week you want to load times to (DD-MM-YYYY): ')
        if not date_input:
            _error_and_exit('No date specified, bailing out...')
        try:
            DATE = datetime.datetime.strptime(date_input, '%d-%m-%Y').date()
        except ValueError:
            _error_and_exit('Provided value didn\'t match the DD-MM-YYYY format')

    week_start, week_end = calculate_week(DATE)
    print 'Attempting to load time data starting at %s and up to %s ...' % (week_start, week_end)
    user_id = _get_user_id(token, url)
    remote_projects = _get_projects(token, url)
    if not remote_projects:
        _error_and_exit('No remote projects are viewable by you')
    for project, milestones in conf.items():
        if not milestones.values():
            continue
        matched_projects = [ _ for _ in remote_projects if project.lower() in _['name'].lower() ]
        if not matched_projects:
            continue
        # print matched_projects
        for matched_project in matched_projects:
            remote_milestones = _get_milestones(token, url, matched_project['id'])
            for milestone in milestones:
                matched_milestones = [ _ for _ in remote_milestones if milestone.lower() in _['name'].lower() ]
                if not matched_milestones:
                    continue
                # print matched_milestones
                for matched_milestone in matched_milestones:
                    remote_tickets = _get_tickets(token, url, matched_project['id'], matched_milestone['id'])
                    for ticket in milestones.values():
                        for ticket_name, ticket_time in ticket.items():
                            matched_tickets = [ _ for _ in remote_tickets if ticket_name.lower() in _['name'].lower() ]
                            if not matched_tickets:
                                continue
                            # print matched_tickets
                            for matched_ticket in matched_tickets:
                                if COMMIT:
                                    for record_date in date_range(week_start, week_end):
                                        ticket_description = matched_ticket['name']
                                        _add_time_record(token, url, user_id, matched_project['id'],
                                            matched_ticket['ticket_id'], ticket_description, str(record_date), ticket_time)

if __name__ == '__main__':
    conf = load_configuration(CONF_FILE)
    main(API_TOKEN, API_URL, conf)
