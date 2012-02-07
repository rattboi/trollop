from urllib import urlencode
import httplib2
import json
import isodate




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

    def __init__(self, conn, obj_id, data=None):
        self.id = obj_id
        self.conn = conn
        self.path = self._prefix + obj_id

        # If we've been passed the data, then remember it and don't bother
        # fetching later.
        if data:
            self._data = data

    def __getattr__(self, attr):
        # For attributes specified in self._attrs, query Trello upon access
        if (attr == '_data' or attr in self._attrs):
            if not '_data' in self.__dict__:
                self._data = json.loads(self.conn.get(self.path))

            # '_data' is special-cased, since it can be looked up on its own,
            # but is also the source of our other dynamic attributes.
            if attr == '_data':
                return self._data
            elif attr in self._data:
                return self._data[attr]

            raise AttributeError("Trello data has no '%s' key" % attr)
        else:
            raise AttributeError("%r object has no attribute %r" %
                                 (type(self).__name__, attr))


class Closable(object):
    def close(self):
        path = self._prefix + self.id + '/closed'
        params = {'value': 'true'}
        result = self.conn.put(path, params=params)


class TrelloField(object):

    def get_instance(self, conn, obj_id):
        return get_class(self.cls)(conn, obj_id)


class ObjectField(TrelloField):
    """
    Maps an idSomething string attr on an object to another object type.
    """

    def __init__(self, key=None, cls=None):

        self.key = key
        self.cls = cls

    def __get__(self, instance, owner):
        return self.get_instance(instance.conn, instance._data[self.key])


class ListField(ObjectField):
    """
    Like an ObjectField, but a list of them.  For fleshing out things like
    idMembers.
    """

    def __get__(self, instance, owner):
        ids = instance._data[self.key]
        conn = instance.conn
        return [self.get_instance(conn, id) for id in ids]

class DateField(TrelloField):
    def __init__(self, key):
        self.key = key

    def __get__(self, instance, owner):
        strdata = instance._data[self.key]
        return isodate.parse_datetime(strdata)


class SubList(TrelloField):
    """
    Kinda like a ListField, but for things listed under a URL subpath (like
    /boards/<id>/cards), as opposed to a list of ids in the document body
    itself.
    """

    def __init__(self, cls):
        # cls may be a name of a class, or the class itself
        self.cls = cls

    def __get__(self, instance, owner):
        if not hasattr(self, '_list'):
            cls = get_class(self.cls)
            path = instance._prefix + instance.id + cls._prefix
            data = json.loads(instance.conn.get(path))
            self._list = [cls(instance.conn, d['id'], d) for d in data]
        return self._list


class Action(LazyTrello):

    _prefix = '/actions/'
    _attrs = set([
        'data',
        'type',
        'date',
        'idMemberCreator',
    ])

    date = DateField('date')


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

    actions = SubList('Action')
    cards = SubList('Card')
    checklists = SubList('Checklist')
    members = SubList('Member')

    organization = ObjectField('idOrganization', 'Organization')


class Card(LazyTrello, Closable):

    _prefix = '/cards/'
    _attrs = set([ 'url', 'idList', 'closed', 'name', 'badges',
                  'checkItemStates', 'desc', 'idBoard', 'idMembers', 'labels',
                 ])

    board = ObjectField('idBoard', 'Board')
    list = ObjectField('idList', 'List')

    members = ListField('idMembers', 'Member')


class Checklist(LazyTrello):

    _prefix = '/checklists/'
    _attrs = set([ 'checkitems', 'idBoard', 'name', ])

    board = ObjectField('idBoard', 'Board')

    cards = SubList('Card')

    # TODO: provide a nicer API for checkitems.  Figure out where they're
    # marked as checked or not.

    # TODO: Figure out why checklists have a /cards/ subpath in the docs.  How
    # could one checklist belong to multiple cards?


class List(LazyTrello, Closable):

    _prefix = '/lists/'
    _attrs = set([ 'url', 'idBoard', 'closed', 'name' ])

    board = ObjectField('idBoard', 'Board')
    cards = SubList('Card')

    # TODO: Generalize this pattern, add it to a base class, and make it work
    # correctly with SubList
    def add_card(self, name, desc=None):
        path = self._prefix + self.id + '/cards'
        body = json.dumps({'name': name, 'idList': self.id, 'desc': desc,
                           'key': self.conn.key, 'token': self.conn.token})
        data = json.loads(self.conn.post(path, body=body))
        card = Card(self.conn, data['id'], data)
        return card


class Member(LazyTrello):

    _prefix = '/members/'
    _attrs = set([ 'url', 'fullName', 'bio', 'gravatar', 'username', ])

    actions = SubList('Action')
    boards = SubList('Board')
    cards = SubList('Card')
    notifications = SubList('Notification')
    organizations = SubList('Organization')


class Notification(LazyTrello):

    _prefix = '/notifications/'
    _attrs = set([ 'data', 'date', 'idMemberCreator', 'type', 'unread', ])

    creator = ObjectField('idMemberCreator', 'Member')


class Organization(LazyTrello):

    _prefix = '/organizations/'
    _attrs = set([ 'url', 'desc', 'displayName', 'name', ])

    actions = SubList('Action')
    boards = SubList('Board')
    members = SubList('Member')
