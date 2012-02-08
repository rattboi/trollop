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
    # The Trello API path where objects of this type may be found. eg '/cards/'
    @property
    def _prefix(self):
        raise NotImplementedError, "LazyTrello subclasses MUST define a _prefix"

    def __init__(self, conn, obj_id, data=None):
        self._id = obj_id
        self._conn = conn
        self._path = self._prefix + obj_id

        # If we've been passed the data, then remember it and don't bother
        # fetching later.
        if data:
            self._data = data

    def __getattr__(self, attr):
        if attr == '_data':
            # Something is trying to access the _data attribute.  If we haven't
            # fetched data from Trello yet, do so now.  Cache the result on the
            # object.
            if not '_data' in self.__dict__:
                self._data = json.loads(self._conn.get(self._path))

            return self._data
        else:
            raise AttributeError("%r object has no attribute %r" %
                                 (type(self).__name__, attr))


class Closable(object):
    """
    Mixin for Trello objects for which you're allowed to PUT to <id>/closed.
    """
    def close(self):
        path = self._prefix + self._id + '/closed'
        params = {'value': 'true'}
        result = self._conn.put(path, params=params)


class Field(object):
    """
    A simple field on a Trello object.  Maps the attribute to a key in the
    object's _data dict.
    """
    # Accessing obj._data will trigger a fetch from Trello if _data isn't
    # already present.

    def __init__(self, key):
        self.key = key

    def __get__(self, instance, owner):
        return instance._data[self.key]


class DateField(Field):

    def __get__(self, instance, owner):
        strdata = instance._data[self.key]
        return isodate.parse_datetime(strdata)


class ObjectField(Field):
    """
    Maps an idSomething string attr on an object to another object type.
    """

    def __init__(self, key, cls):

        self.key = key
        self.cls = cls

    def __get__(self, instance, owner):
        return self.related_instance(instance._conn, instance._data[self.key])

    def related_instance(self, conn, obj_id):
        return get_class(self.cls)(conn, obj_id)


class ListField(ObjectField):
    """
    Like an ObjectField, but a list of them.  For fleshing out things like
    idMembers.
    """

    def __get__(self, instance, owner):
        ids = instance._data[self.key]
        conn = instance._conn
        return [self.related_instance(conn, id) for id in ids]


class SubList(object):
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
            path = instance._prefix + instance._id + cls._prefix
            data = json.loads(instance._conn.get(path))
            self._list = [cls(instance._conn, d['id'], d) for d in data]
        return self._list

### BEGIN ACTUAL WRAPPER OBJECTS

class Action(LazyTrello):

    _prefix = '/actions/'
    data = Field('data')
    type = Field('type')
    date = DateField('date')
    creator = ObjectField('idMemberCreator', 'Member')


class Board(LazyTrello, Closable):

    _prefix = '/boards/'

    url = Field('url')
    name = Field('name')
    pinned = Field('pinned')
    prefs = Field('prefs')
    desc = Field('desc')
    closed = Field('closed')

    organization = ObjectField('idOrganization', 'Organization')

    actions = SubList('Action')
    cards = SubList('Card')
    checklists = SubList('Checklist')
    lists = SubList('List')
    members = SubList('Member')


class Card(LazyTrello, Closable):

    _prefix = '/cards/'

    url = Field('url')
    closed = Field('closed')
    name = Field('name')
    badges = Field('badges')
    checkItemStates = Field('checkItemStates')
    desc = Field('desc')
    labels = Field('labels')

    board = ObjectField('idBoard', 'Board')
    list = ObjectField('idList', 'List')

    members = ListField('idMembers', 'Member')


class Checklist(LazyTrello):

    _prefix = '/checklists/'
    checkitems = Field('checkitems')
    name = Field('name')
    board = ObjectField('idBoard', 'Board')
    cards = SubList('Card')

    # TODO: provide a nicer API for checkitems.  Figure out where they're
    # marked as checked or not.

    # TODO: Figure out why checklists have a /cards/ subpath in the docs.  How
    # could one checklist belong to multiple cards?


class List(LazyTrello, Closable):

    _prefix = '/lists/'

    closed = Field('closed')
    name = Field('name')
    url = Field('url')
    board = ObjectField('idBoard', 'Board')
    cards = SubList('Card')

    # TODO: Generalize this pattern, add it to a base class, and make it work
    # correctly with SubList
    def add_card(self, name, desc=None):
        path = self._prefix + self._id + '/cards'
        body = json.dumps({'name': name, 'idList': self._id, 'desc': desc,
                           'key': self._conn.key, 'token': self._conn.token})
        data = json.loads(self._conn.post(path, body=body))
        card = Card(self._conn, data['id'], data)
        return card


class Member(LazyTrello):

    _prefix = '/members/'

    url = Field('url')
    fullname = Field('fullName')
    username = Field('username')

    actions = SubList('Action')
    boards = SubList('Board')
    cards = SubList('Card')
    notifications = SubList('Notification')
    organizations = SubList('Organization')


class Notification(LazyTrello):

    _prefix = '/notifications/'

    data = Field('data')
    date = DateField('date')
    type = Field('type')
    unread = Field('unread')

    creator = ObjectField('idMemberCreator', 'Member')


class Organization(LazyTrello):

    _prefix = '/organizations/'

    url = Field('url')
    desc = Field('desc')
    displayname = Field('displayName')
    name = Field('name')

    actions = SubList('Action')
    boards = SubList('Board')
    members = SubList('Member')
