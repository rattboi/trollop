import unittest
import json
import urlparse

from trollop import TrelloConnection


class Namespace(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self


class FakeHttp(object):
    """Mock for httplib2.Http.  Should be initted with a dict that looks like
    an httplib2 response, and a dict representing the server side data, keyed
    by url path."""

    def __init__(self, response, data):
        self.response = response
        self.data = data
        # store requests in this list so they can be inspected later.
        self.requests = []

    def request(self, url, method, *args, **kwargs):
        path = urlparse.urlparse(url).path
        self.requests.append(locals())
        try:
            return Namespace(self.response), json.dumps(self.data[path])
        except KeyError:
            return Namespace({'status': 404}), "Not found"


class TrollopTestCase(unittest.TestCase):

    response = {'status': 200}
    data = {}

    def setUp(self):
        self.conn = TrelloConnection('blah', 'blerg')
        # monkeypatch the http client
        self.conn.client = FakeHttp(self.response, self.data)


class TestGetMe(TrollopTestCase):

    data = {'/1/members/me': {
        "id":"4e73a7ef5571166c5f53a93f",
        "fullName":"Brent Tubbs",
        "username":"btubbs",
        "gravatar":"e60b3c53235cd53f5e2b6401678c4f6a",
        "bio":"",
        "url":"https://trello.com/btubbs"
    }}

    def test(self):

        # Ensure that the connection has a 'me' property, with attributes for
        # the json keys returned in the response.  Accessing this attribute
        # will also force an http request
        assert self.conn.me.username == self.data['/1/members/me']['username']

        # Make sure that client.request was called with the right path and
        # method, by inspecting the list of requests made to the mock.
        req1 = self.conn.client.requests[0]
        assert req1['url'].startswith('https://api.trello.com/1/members/me')
        assert req1['method'] == 'GET'

class SublistTests(TrollopTestCase):
    data = {'/1/members/me/boards/':
                [{'id': 'fakeboard1', 'name': 'Fake Board 1'},
                 {'id': 'fakeboard2', 'name': 'Fake Board 2'}],
            '/1/boards/fakeboard1/lists/':
                [{'id': 'fakeboard1_fakelist', 'idBoard': 'fakeboard1', 'name':
                  'Fake List from Fake Board 1'}],
            '/1/boards/fakeboard2/lists/':
                [{'id': 'fakeboard2_fakelist', 'idBoard': 'fakeboard2', 'name':
                  'Fake List from Fake Board 2'}]}

    def test_cache_bug_fixed(self):
        # assert that fakeboard1 and fakeboard2 have distinct sublists.
        # Fixes https://bitbucket.org/btubbs/trollop/changeset/36e3c41c7016
        assert (self.conn.me.boards[0].lists[0].name ==
                'Fake List from Fake Board 1')
        assert (self.conn.me.boards[1].lists[0].name ==
                'Fake List from Fake Board 2')

