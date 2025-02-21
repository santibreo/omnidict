.. note::
  To get a better overview visit `key-value documentation webpage <https://santibreo.github.io/key-value/index.html>`_.


########
Omnidict
########

Opinionated interface for many key/value repositories:

  I am kind of tired of having to do small changes when I move from Dictionary, to Redis, to Shelve or whatever key/value storage I am using. This is an interface heavily inspired by `builtin shelve module <https://docs.python.org/3/library/shelve.html>`_ to make all those `mapping` repositories  behave the same way:

* **Get item**: ``storage['key']`` returns the value associated to ``'key'`` and raises a ``KeyError`` if ``'key'`` is not defined. ``storage.get('key')`` behaves the same way but returns ``default()`` when ``'key'`` is not defined.

* **Set item**: ``storage['key'] = val`` associates ``val`` to ``'key'`` and raises a ``KeyError`` if ``'key'`` already has a value associated. ``storage.set('key', val)`` behaves the same way but overwrites association if it already exists.

* **Delete item**: ``del storage['key']`` deletes ``'key'`` and raises a ``KeyError`` if ``'key'`` is not defined. ``storage.delete('key')`` behaves the same way but does nothing when ``'key'`` is not defined.

* **Expiration**: You can define ``expire_seconds`` parameter to make your associations expire. Expiration time is refreshed every time you access a key.

* **Encryption**: You can define a ``passphrase`` parameter to encrypt your values using symmetric encryption.
