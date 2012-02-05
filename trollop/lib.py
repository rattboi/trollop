from urllib import urlencode

import httplib2
import json


class TrelloError(Exception):
    pass


class TrelloConnection(object):

    def __init__(self, api_key, oauth_token):
        self.client = httplib2.Http()
        self.key = api_key
        self.token = oauth_token

    def request(self, method, path, params=None, body=None):
        headers = {'Accept': 'application/json'}
        if method == 'POST' or method == 'PUT':
            headers.update({'Content-Type': 'application/json'})

        if not path.startswith('/'):
            path = '/' + path
        url = 'https://api.trello.com/1' + path

        params = params or {}
        params.update({'key': self.key, 'token': self.token})
        url += '?' + urlencode(params)
        response, content = self.client.request(url, method,
                                                headers=headers,body=body)
        if response.status != 200:
            # TODO: confirm that Trello never returns a 201, for example, when
            # creating a new object. If it does, then we shouldn't restrict
            # ourselves to a 200 here.
            raise TrelloError(content)
        return content

    def get(self, path, params=None):
        return self.request('GET', path, params)

    def post(self, path, params=None, body=None):
        return self.request('POST', path, params, body)

    def put(self, path, params=None, body=None):
        return self.request('PUT', path, params, body)

    def get_board(self, board_id):
        return Board(self, board_id)

    def get_list(self, list_id):
        return List(self, list_id)

    def get_card(self, card_id):
        return Card(self, card_id)

    def get_member(self, member_id):
        return Member(self, member_id)

    @property
    def me(self):
        """
        Return a Membership object for the user whose credentials were used to
        connect.
        """
        return Member(self, 'me')


class LazyTrello(object):
    """
    Parent class for Trello objects (cards, lists, boards, members, etc).  This
    should always be subclassed, never used directly.
    """
    # The Trello API path where objects of this type may be found.
    _prefix = '' # eg '/cards/'

    # In subclasses, these values should be filled in with a set of the
    # attribute names that class has data for, and the path prefix like
    # '/cards/'.  A set is used instead of a list in order to provide more
    # efficient 'in' tests.  These are the attributes that will trigger an http
    # GET before trying to return a value.
    _attrs = set() # eg set(['name', 'url'])

    # Here you can specify related objects that can be looked up on a sub-path
    # of the object you've got.  Use the name of the subpath as the key
    # (without any slashes), and the class to use to instantiate those objects
    # as the value.  If you run into a class declaration ordering problem, you
    # can also put the name of the class in a string and use that for the
    # value.
    _sublists = {} # eg {'boards': Board} or {'boards': 'Board'}

    def __init__(self, conn, obj_id, data=None):
        self.id = obj_id
        self.conn = conn
        self.path = self._prefix + obj_id

        # If we've been passed the data, then remember it and don't bother
        # fetching later.
        if data:
            self.data = data

    def __getattr__(self, attr):
        # For attributes specified in self._attrs, query Trello upon
        # access
        if (attr == 'data' or
           attr in self._attrs or
           attr in self._sublists):
            if not 'data' in self.__dict__:
                self.data = json.loads(self.conn.get(self.path))

            # 'data' is special-cased, since it can be looked up on its own,
            # but is also the source of our other dynamic attributes.
            if attr == 'data':
                return self.data
            elif attr in self.data:
                return self.data[attr]
            elif attr in self._sublists:
                # classes may be values right in the dict, or may be identified
                # by name as strings (for cases where you want to reference a
                # class that's not defined yet.)
                if isinstance(self._sublists[attr], str):
                    klass = globals()[self._sublists[attr]]
                else:
                    klass = self._sublists[attr]
                path = self._prefix + self.id + '/' + attr
                data = json.loads(self.conn.get(path))
                # TODO: cache these on the object so you don't have to do
                # multiple http requests if, for example, list.cards is called
                # multiple times on the same object.
                return [klass(self.conn, d['id'], d) for d in data]

            raise AttributeError("Trello data has %s key" % attr)
        else:
            raise AttributeError("%r object has no attribute %r" %
                                 (type(self).__name__, attr))

    # FIXME: Not all objects are closable.  This should be moved to a mixin.
    def close(self):
        path = self._prefix + self.id + '/closed'
        params = {'value': 'true'}
        result = self.conn.put(path, params=params)


class Board(LazyTrello):

    _prefix = '/boards/'

    _attrs = set([
        'url',
        'name',
        'pinned',
        'prefs',
        'desc',
        'closed',
        'idOrganization',
    ])

    _sublists = {
        'members': 'Member',
    }

    def all_lists(self):
        """Returns all lists on this board"""
        return self.get_lists('all')

    def open_lists(self):
        """Returns all open lists on this board"""
        return self.get_lists('open')

    def closed_lists(self):
        """Returns all closed lists on this board"""
        return self.get_lists('closed')

    def get_lists(self, filtr):
        # 'filter' is a Python built in function, so we misspell here to avoid
        # clobbering it.

        path = self.path + '/lists'
        params = {'cards': 'none', 'filter': filtr}
        data = json.loads(self.conn.get(path, params))

        return [List(self.conn, ldata['id'], ldata) for ldata in data]


class List(LazyTrello):

    _prefix = '/lists/'
    _attrs = set([
        'url',
        'idBoard',
        'closed',
        'name'
    ])
    _sublists = {
        'cards': 'Card',
    }


    def add_card(self, name, desc=None):
        path = self._prefix + self.id + '/cards'
        body = json.dumps({'name': name, 'idList': self.id, 'desc': desc,
                           'key': self.conn.key, 'token': self.conn.token})
        data = json.loads(self.conn.post(path, body=body))
        card = Card(self.conn, data['id'], data)
        return card


class Card(LazyTrello):

    _prefix = '/cards/'
    _attrs = set([
        'url',
        'idList',
        'closed',
        'name',
        'badges',
        'checkItemStates',
        'desc',
        'idBoard',
        'idMembers',
        'labels',
    ])

    # XXX: This is a common pattern.  Make it generic? Possibly with
    # '_properties'
    @property
    def board(self):
        return Board(self.conn, self.idBoard)

    @property
    def list(self):
        return List(self.conn, self.idList)

    # XXX: Another common pattern.  Maybe add magic for '_lists'
    @property
    def members(self):
        return [Member(self.conn, mid) for mid in self.idMembers]


class Member(LazyTrello):

    _prefix = '/members/'
    _attrs = set([
        'url',
        'fullName',
        'bio',
        'gravatar',
        'username',
    ])
    _sublists = {
        'boards': Board,
        'cards': Card,
    }


class Organization(LazyTrello):

    _prefix = '/organizations/'
    _attrs = set([
        'url',
        'desc',
        'displayName',
        'name',
    ])
    _sublists = {
        'boards': Board,
        'members': Member,
    }

# TODO: implement the rest of the objects, and their methods.  Given the
# patterns above, that should just mean more typing, at this point.
