Meet Trollop
============

Trollop is a Python library for working with the `Trello API`_.

Quick Start
===========

A Trello connection is instantiated with your `API key`_ and a user's `oauth token`_::

    In [1]: from trollop import TrelloConnection

    In [2]: conn = TrelloConnection(<your developer key>, <user's oauth token>)

The connection object will automatically have a Member object attached,
representing the user whose oauth token was used to connect::

    In [3]: conn.me
    Out[3]: <trollop.lib.Member object at 0x101707650>

    In [4]: conn.me.username
    Out[4]: u'btubbs'

In the previous example no HTTP request was made until command 4, the access
to conn.me.username.  Trollop objects are lazy.

The connection object has methods for getting objects by their IDs::

    In [5]: card = conn.get_card('4f2e454cefab2bbd4ea71b02')

    In [6]: card.name
    Out[6]: u'Build a Python Trello Library'

    In [7]: card.desc
    Out[7]: u'And call it Trollop.'

You can use normal Python introspection techniques to see the available
attributes.  They'll mostly be named exactly as they are in the JSON returned
from Trello::

    In [13]: dir(card)
    Out[13]: 
    ['__class__',
     '__delattr__',
     '__dict__',
     '__doc__',
     '__format__',
     '__getattr__',
     '__getattribute__',
     '__hash__',
     '__init__',
     '__module__',
     '__new__',
     '__reduce__',
     '__reduce_ex__',
     '__repr__',
     '__setattr__',
     '__sizeof__',
     '__str__',
     '__subclasshook__',
     '__weakref__',
     '_conn',
     '_id',
     '_path',
     '_prefix',
     'badges',
     'board',
     'checkItemStates',
     'close',
     'closed',
     'desc',
     'labels',
     'list',
     'members',
     'name',
     'url']


There are convenience properties to automatically look up related
objects::

    In [9]: lst = card.list

    In [10]: lst
    Out[10]: <trollop.lib.List object at 0x101707890>

    In [11]: lst.name
    Out[11]: u'Icebox'

    In [12]: lst.id
    Out[12]: u'4f17cb04d5c817032301c179'

    In [13]: len(lst.cards)
    Out[13]: 20

    In [14]: lst.cards[-1].name
    Out[14]: u'Build a Python Trello Library'

Help Wanted
===========

Coverage for creating/updating objects is still really thin.  If you'd like to
pitch in to finish covering the whole API, please send a pull request with your
changes.

License
=======

Trollop is licensed under the `MIT License`_.

.. _Trello API: https://trello.com/docs/api/index.html
.. _API key: https://trello.com/card/board/generating-your-developer-key/4ed7e27fe6abb2517a21383d/4eea75831576578f2713f460
.. _oauth token: https://trello.com/card/board/getting-a-user-token-and-oauth-urls/4ed7e27fe6abb2517a21383d/4eea75bc1576578f2713fc5f 
.. _MIT License: http://www.opensource.org/licenses/mit-license.php
