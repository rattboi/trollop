from urllib import urlencode

import httplib2
import json




def get_class(str_or_class):
    """Accept a name or actual class object for a class in the current module.
    Return a class object."""
    if isinstance(str_or_class, str):
        return globals()[str_or_class]
    else:
        return str_or_class


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

    def get_card(self, card_id):
        return Card(self, card_id)

    def get_list(self, list_id):
        return List(self, list_id)

    def get_member(self, member_id):
        return Member(self, member_id)

    def get_notification(self, not_id):
        return Notification(self, not_id)

    def get_organization(self, org_id):
        return Organization(self, org_id)

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

    # These are related objects that need to be instantiated with a particular
    # field from the current object as their id.  For example, a Card object
    # has a property for the Board to which it belongs.  This is a little more
    # complicated than our other magic because 3 pieces of data are involved:
    # the name of the attribute as accessed, the name of the field containing
    # the ID, and the name of the class that should be instantiated with the
    # id.  Example:
    # _properties = {'board': Related('idBoard', 'Board')}
    _properties = {}

    # Here you can specify related objects that can be looked up on a sub-path
    # of the object you've got.  Use the name of the subpath as the key
    # (without any slashes), and the class to use to instantiate those objects
    # as the value.  If you run into a class declaration ordering problem, you
    # can also put the name of the class in a string and use that for the
    # value.
    _sublists = {} # eg {'actions': Action} or {'actions': 'Action'}


    def __init__(self, conn, obj_id, data=None):
        self.id = obj_id
        self.conn = conn
        self.path = self._prefix + obj_id

        # If we've been passed the data, then remember it and don't bother
        # fetching later.
        if data:
            self._data = data

    def __getattr__(self, attr):
        # For attributes specified in self._attrs, query Trello upon
        # access
        if (attr == '_data' or
           attr in self._attrs or
           attr in self._sublists or
           attr in self._properties):
            if not '_data' in self.__dict__:
                self._data = json.loads(self.conn.get(self.path))

            # '_data' is special-cased, since it can be looked up on its own,
            # but is also the source of our other dynamic attributes.
            if attr == '_data':
                return self._data
            elif attr in self._data:
                return self._data[attr]
            elif attr in self._properties:
                prop = self._properties[attr]
                return prop.get_instance(self.conn, self._data[prop.field])
            elif attr in self._sublists:
                # classes may be values right in the dict, or may be identified
                # by name as strings (for cases where you want to reference a
                # class that's not defined yet.)
                klass = get_class(self._sublists[attr])
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


class Closable(object):
    def close(self):
        path = self._prefix + self.id + '/closed'
        params = {'value': 'true'}
        result = self.conn.put(path, params=params)


class Related(object):
    """Maps an idSomething string attr on an object to another object type."""

    def __init__(self, field, cls):
        # cls may be a name of a class, or the class itself
        self.field = field
        self.cls = cls

    def get_instance(self, conn, obj_id):
        return get_class(self.cls)(conn, obj_id)


class Action(LazyTrello):

    _prefix = '/actions/'
    _attrs = set([
        'data',
        'type',
        'date',
        'idMemberCreator',
    ])

    # TODO: override the default date property and provide a version that
    # returns a Python datetime.


class Board(LazyTrello, Closable):

    _prefix = '/boards/'

    _attrs = set([
        'url',
        'name',
        'pinned',
        'prefs',
        'desc',
        'closed',
        'idOrganization',
        'prefs',
    ])

    _sublists = {
        'actions': 'Action',
        'cards': 'Card',
        'checklists': 'Checklist',
        'lists': 'List',
        'members': 'Member',
    }

    _properties = {
        # FIXME: organization might not be present.  Not sure how to handle that
        # yet.
        'organization': Related('idOrganization', 'Organization'),
    }


class Card(LazyTrello, Closable):

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
    _properties = {
        'board': Related('idBoard', 'Board'),
        'list': Related('idList', 'List'),
    }

    # XXX: Another common pattern.  Maybe add magic for '_lists'
    @property
    def members(self):
        return [Member(self.conn, mid) for mid in self.idMembers]


class Checklist(LazyTrello):
    _prefix = '/checklists/'

    _attrs = set([
        'checkitems',
        'idBoard',
        'name',
    ])

    _properties = {
        'board': Related('idBoard', 'Board')
    }

    _sublists = {
        'cards': Card,
    }

    # TODO: provide a nicer API for checkitems.  Figure out where they're
    # marked as checked or not.

    # TODO: Figure out why checklists have a /cards/ subpath in the docs.  How
    # could one checklist belong to multiple cards?


class List(LazyTrello, Closable):

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
    _properties = {
        'board': Related('idBoard', 'Board'),
    }

    # TODO: implement a 'cards' list like the 'members' list that Board has.


    def add_card(self, name, desc=None):
        path = self._prefix + self.id + '/cards'
        body = json.dumps({'name': name, 'idList': self.id, 'desc': desc,
                           'key': self.conn.key, 'token': self.conn.token})
        data = json.loads(self.conn.post(path, body=body))
        card = Card(self.conn, data['id'], data)
        return card


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
        'actions': Action,
        'boards': Board,
        'cards': Card,
        'notifications': 'Notification',
        'organizations': 'Organization',
    }


class Notification(LazyTrello):
    _prefix = '/notifications/'
    _attrs = set([
        'data',
        'date',
        'idMemberCreator',
        'type',
        'unread',
    ])
    _properties = {
        'creator': Related('idMemberCreator', 'Member'),
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
        'actions': Action,
        'boards': Board,
        'members': Member,
    }
