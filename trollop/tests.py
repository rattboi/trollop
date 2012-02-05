import unittest
import json
from trollop import TrelloConnection


class Namespace(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self


class FakeHttp(object):
    """Mock for httplib2.Http"""

    def __init__(self, response, content):
        self.response = response
        self.content = content
        # store requests in this list so they can be inspected later.
        self.requests = []

    def request(self, *args, **kwargs):
        self.requests.append(locals())
        return Namespace(self.response), self.content


class TrollopTestCase(unittest.TestCase):

    response = {'status': 200}
    content = {}

    def setUp(self):
        self.conn = TrelloConnection('blah', 'blerg')
        # monkeypatch the http client
        self.conn.client = FakeHttp(self.response, json.dumps(self.content))


class TestGetMe(TrollopTestCase):

    content = {
        "id":"4e73a7ef5571166c5f53a93f",
        "fullName":"Brent Tubbs",
        "username":"btubbs",
        "gravatar":"e60b3c53235cd53f5e2b6401678c4f6a",
        "bio":"",
        "url":"https://trello.com/btubbs"
    }

    def test_get_me(self):

        # Ensure that the connection has a 'me' property, with attributes for
        # the json keys returned in the response.  Accessing this attribute
        # will also force an http request
        assert self.conn.me.username == self.content['username']

        # Make sure that client.request was called with the right path and
        # method, by inspecting the list of requests made to the mock.
        req1 = self.conn.client.requests[0]
        assert req1['args'][0].startswith('https://api.trello.com/1/members/me')
        assert req1['args'][1] == 'GET'
