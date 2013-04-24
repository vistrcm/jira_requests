jira_requests
=============

Simple tool to make REST API requests to jira.

Requirements
------------
This script is working in Python3.

[requests](python-requests.org)

Config
------
By default config file contains user credentials. ~/.jira_requests

```
[http://server]
username=super_admin
password=very_long_password
```

Usage
-----

Only search action supported by now

```
python jira_requests.py search <JQL>
```

example:

```
python jira_requests.py search "assignee = currentUser()"
```
