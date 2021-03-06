#!/sbin/venv python
"""package for simplify common work with Jira"""

import requests
import json
import logging
import os
import getpass
import configparser
import functools
import argparse
import concurrent.futures as futures

SERVER = 'http://jira'
API_PATH = '/rest/api/'
API_VER = '2.0.alpha1'
URL = '{server}{api_path}{api_ver}'.format(
    server=SERVER,
    api_path=API_PATH,
    api_ver=API_VER
)
CONFIG_FILE = os.path.expanduser("~/.jira_requests")

LOGGING_LEVEL = logging.INFO
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
fh = logging.FileHandler('jira_requests.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)


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
        logger.debug("issue cache_info: {}".format(
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
        logger.debug("auth request.text: {}".format(request.text))

    def __request(self, url=None, path=None, params=None, request_type='GET'):
        """Actual method which make http request"""

        if url is None:
            url = self.url

        if path is not None:
            url = url + path

        if request_type is 'GET':

            logger.debug('GETting {} with params {}'.format(url, params))

            request = self._session.get(url,
                                        params=params)

        elif request_type is 'POST':

            headers = {'Content-Type': 'application/json'}

            logger.debug('POSTing {} with params {}'.format(url, params))
            request = self._session.post(url,
                                         data=json.dumps(params),
                                         headers=headers)

        else:
            raise Exception('Unsupported request_type', request_type)

        return request.json()

    def __search(self, jql=None):
        """search for issues"""

        logger.info("jql = {}".format(jql))
        issues = []
        if jql is not None:
            start_at = 0
            max_results = 50
            total = 1000000

            # some logging for debug
            logger.debug("initial start_at = {}".format(start_at))
            logger.debug("initial max_results = {}".format(max_results))
            logger.debug("initial total = {}".format(total))

            while True:
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results
                }

                result = self.__request(path='/search',
                                        params=params,
                                        request_type='POST')
                logger.debug("search result: {}".format(result['issues']))

                issues = issues + result['issues']

                # some logging for debug
                logger.debug("step start_at = {}".format(start_at))
                logger.debug("step max_results = {}".format(max_results))
                logger.debug("step total = {}".format(total))

                if start_at + max_results >= total:
                    logger.debug("breaking search loop.")
                    break

                start_at += max_results
                total = result['total']
                logger.debug("Search not finished. Continue")

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

    return username, password


def search_command(args):
    """search command executed"""
    logger.info("going to search something: {}".format(args))

    username, password = get_cred()

    jira = Jira(URL, username, password)
    issues = jira.search_issues(args.jql)

    for issue in issues:
        print("{id}\t{name}\t{priority}\t{status}\t{assignee}".format(
            id=issue.key,
            name=issue.field('summary'),
            priority=issue.field('priority'),
            status=issue.field('status'),
            assignee=issue.field('assignee', sub='displayName')))

def search_command_parallel(args):
    """Parallel search command executed"""
    def issue_to_print(issue):
        issue_str = "{id}\t{name}\t{priority}\t{status}\t{assignee}".format(
            id=issue.key,
            name=issue.field('summary'),
            priority=issue.field('priority'),
            status=issue.field('status'),
            assignee=issue.field('assignee', sub='displayName'))
        return issue_str

    logger.info("going to search something: {}".format(args))

    username, password = get_cred()
    jira = Jira(URL, username, password)
    issues_list = jira.search_issues(args.jql)

    issues_to_print = {}
    # With statement to ensure threads are cleaned up promptly
    with futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Start the load operations and mark each future with its issue key
        future_to_issue = {executor.submit(issue_to_print, issue): issue.key for issue in issues_list}
        for future in futures.as_completed(future_to_issue):
            issue_str = future_to_issue[future]
            try:
                data = future.result()
            except Exception as exc:
                logger.error('%r generated an exception: %s', issue_str, exc)
            else:
                logger.debug('%r page is %s', issue_str, data)
                issues_to_print[issue_str] = data

    for issue in issues_list:
        print(issues_to_print[issue.key])



def show_command(args):
    """show command executed"""
    print("show: {}".format(args))
    print("Not implemented yet")


def main():
    """parse command line args"""
    parser = argparse.ArgumentParser('jira_requests utility')

    parser.add_argument("-d", "--debug", help="debug output",
                        action="store_true")

    subparsers = parser.add_subparsers(title='subcommands',
                                       dest='subparser_name',
                                       description='valid subcommands',
                                       help='additional sub-command help')

    # create parser for "search" command
    parser_search = subparsers.add_parser('search', help='search for issues')
    parser_search.add_argument('jql', help='JQL to execute')
    # parser_search.set_defaults(func=search_command)
    parser_search.set_defaults(func=search_command_parallel)

    # create parser for "show" command
    parser_show = subparsers.add_parser('show', help='show issue')
    parser_show.add_argument('ticket_id', help='JIRA issue id to show')
    parser_show.set_defaults(func=show_command)

    args = parser.parse_args()

    # check for debug
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("debug logging level turned on")

    # execute required function
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("program was interrupted by KeyboardInterrupt")
