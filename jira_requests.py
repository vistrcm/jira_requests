#!/sbin/venv python
"""package for simplify commont work with Jira"""

import requests
import json
import logging
import os
import getpass
import configparser
import functools

SERVER = 'http://jira'
API_PATH = '/rest/api/'
API_VER = '2.0.alpha1'
URL = '{server}{api_path}{api_ver}'.format(
    server=SERVER,
    api_path=API_PATH,
    api_ver=API_VER
)
CONFIG_FILE = os.path.expanduser("~/.jira_requests")

logging.basicConfig(
    filename='jira_requests.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# logging.basicConfig(level=logging.INFO)


class Issue:
    """Issue class is representation of Jira issue."""

    def __init__(self, jira=None, key=None, issue_self=None):
        self.jira = jira
        self.key = key
        self.issue_self = issue_self

    def field(self, field_name, sub=None):
        """method to get values of different fields"""

        def get_subfield(field, sub):
            """get subfield value or raise ecxeption"""
            if sub in field:
                return field[sub]
            else:
                raise Exception('Unsupported fields in value dictionary',
                                field_value)

        issue = self.jira.issue(self.issue_self)
        logging.debug("issue cache_info: {}".format(
            self.jira.issue.cache_info()))

        field_value = issue['fields'][field_name]['value']

        # a lot of ifs
        if isinstance(field_value, dict):
            if sub is not None:
                result = get_subfield(field_value, sub)
            else:
                result = get_subfield(field_value, 'name')
        elif isinstance(field_value, str):
            result = field_value
        else:
            raise Exception('Unsupported type of value field', field_value)

        return result


class Jira:
    """Representation of Jira"""

    def __init__(self, url=None, user=None, passwd=None):
        self.url = url
        self.user = user
        self.passwd = passwd
        self._session = requests.Session()

        # auth
        headers = {'Content-Type': 'application/json'}
        auth = {
            "username": self.user,
            "password": self.passwd
        }

        request = self._session.post('http://jira/rest/auth/1/session',
                                     headers=headers,
                                     data=json.dumps(auth))
        logging.debug("auth request.text: {}".format(request.text))

    def __request(self, url=None, path=None, params=None, request_type='GET'):
        """Actuall method which make http request"""

        if url is None:
            url = self.url

        if path is not None:
            url = url + path

        if request_type is 'GET':

            logging.debug('GETting {} with params {}'.format(url, params))

            request = self._session.get(url,
                                        params=params)

        elif request_type is 'POST':

            headers = {'Content-Type': 'application/json'}

            logging.debug('POSTing {} with params {}'.format(url, params))
            request = self._session.post(url,
                                         data=json.dumps(params),
                                         headers=headers)

        else:
            raise Exception('Unsupported request_type', request_type)

        return request.json()

    def __search(self, jql=None):
        """search for issues"""

        logging.info("jql = {}".format(jql))
        issues = []
        if jql is not None:
            start_at = 0
            max_results = 50
            total = 1000000

            # some logging for debug
            logging.debug("initial start_at = {}".format(start_at))
            logging.debug("initial max_results = {}".format(max_results))
            logging.debug("initial total = {}".format(total))

            while True:
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results
                }

                result = self.__request(path='/search',
                                      params=params,
                                      request_type='POST')
                logging.debug("search result: {}".format(result['issues']))

                issues = issues + result['issues']

                # some logging for debug
                logging.debug("step start_at = {}".format(start_at))
                logging.debug("step max_results = {}".format(max_results))
                logging.debug("step total = {}".format(total))

                if start_at + max_results >= total:
                    logging.debug("breaking search loop.")
                    break

                start_at += max_results
                total = result['total']
                logging.debug("Search not finished. Continue")

        else:
            raise Exception('JQL string not set')

        return issues

    def search_issues(self, jql=None):
        search_results = self.__search(jql)

        issues = [Issue(self, issue['key'], issue['self'])
                  for issue in search_results]
        return issues

    @functools.lru_cache(maxsize=6)
    def issue(self, url=None):
        result = self.__request(url)
        return result


def get_cred():
    """Get credentials from user.

    :return: (username, password)"""

    # first try to parse config file
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        username = config.get(SERVER, "username")
        password = config.get(SERVER, "password")
    except Exception as e:
        print("exception on getting data from config: %s" % e)
        print("asking user")
        # get auth info from user
        username = input('input username: ')
        password = getpass.getpass(prompt='input password: ')

    return (username, password)


def main():
    """start programm"""
    username, password = get_cred()

    jira = Jira(URL, username, password)
    issues = jira.search_issues("assignee = currentUser()")

    for issue in issues:
        print("{id}\t{name}\t{priority}\t{status}\t{assignee}".format(
            id=issue.key,
            name=issue.field('summary'),
            priority=issue.field('priority'),
            status=issue.field('status'),
            assignee=issue.field('assignee', sub='displayName')))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("program was interrupted by KeyboardInterrupt")
