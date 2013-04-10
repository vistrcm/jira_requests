#!/sbin/venv python


import requests
import json
import logging
import os
import getpass
import configparser

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
    def __init__(self, jira=None, key=None, issue_self=None):
        self.jira = jira
        self.key = key
        self.issue_self = issue_self

    def field(self, field_name):
        issue = self.jira.issue(self.issue_self)
        return issue['fields'][field_name]['value']


class Jira:
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

    def request(self, url=None, path=None, params=None, request_type='GET'):

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

    def search(self, jql=None):
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

                result = self.request(path='/search',
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

        else:
            raise Exception('JQL string not set')

        return issues

    def search_issues(self, jql=None):
        search_results = self.search(jql)

        issues = [Issue(self, issue['key'], issue['self'])
                  for issue in search_results]
        return issues

    def issue(self, url=None):
        result = self.request(url)
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
        print("{}\t\t{}".format(issue.key, issue.field('summary')))


if __name__ == "__main__":
    main()
