"""
Storage classes that unifies interactions with key-value stored information
"""
# Builtins
import re
import abc
import json
import pickle
import random
import shelve
import tempfile
from hashlib import md5
from pathlib import Path
from base64 import b64encode
from datetime import datetime, timedelta, timezone
# Installed
from cryptography.fernet import Fernet
# Types
from typing import Any
from typing import Self
from typing import Generic
from typing import TypeVar
from typing import Optional
from typing import Callable
from typing import Iterator
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from redis import Redis


_T = TypeVar('_T')
_SeedType = None | int | float | str | bytes | bytearray


def _now() -> datetime:
    """TZ-aware UTC located now"""
    return datetime.now(tz=timezone.utc)


class KeyValueRepository(abc.ABC, Generic[_T]):
    """Base class for all repositories

    Repositories defined a :attr:`KeyValueRepository.storage` which is the actual
    key-value storage used to memorize data.

    Repositories might define :attr:`KeyValueRepository.expire_seconds` which defines
    the number of seconds a key is preserved in the storage **after last time is was
    gotten**.

    Repositories might define :attr:`KeyValueRepository.default` which ensures that
    :class:`KeyError` is not raised when value requested through
    :meth:`KeyValueRepository.__getitem__` does not exists.
    """

    def __init__(
        self,
        storage: _T,
        /,
        expire_seconds: int = 0,
        passphrase: _SeedType = '',
        *,
        prefix: str = '',
        default: None | Callable[[str], Any] = None
    ):
        self.prefix: str = prefix
        self.storage: _T = storage
        self.expire_seconds: int = expire_seconds
        if default is None:
            self._has_default = False
            self.default = lambda _: None
        else:
            self._has_default = True
            self.default = default
        if not passphrase:
            self._is_encrypted = False
            self.cipher = None
        else:
            self._is_encrypted = True
            self.cipher = self.build_cipher(passphrase)

    @property
    def has_default(self) -> bool:
        return self._has_default

    @property
    def is_encrypted(self) -> bool:
        return self._is_encrypted

    def __repr__(self) -> str:
        return f"{type(self).__name__}(storage={repr(self.storage)})"

    def __init_subclass__(cls: type[Self]) -> None:
        super().__init_subclass__()
        delitem = cls.__delitem__
        cls.__delitem__ = lambda self, key: delitem(self, self.customize_key(key))
        getitem = cls.__getitem__
        cls.__getitem__ = lambda self, key: cls.unserialize_val(
            getitem(self, self.customize_key(key)) if not self.is_encrypted
            else self.cipher.decrypt(getitem(self, self.customize_key(key)))
        )
        setitem = cls.__setitem__
        cls.__setitem__ = lambda self, key, value: setitem(
            self, self.customize_key(key),
            cls.serialize_val(value) if not self.is_encrypted
            else self.cipher.encrypt(cls.serialize_val(value))
        )

    @staticmethod
    def build_cipher(passphrase: _SeedType) -> Fernet:
        random.seed(passphrase)
        return Fernet(key=b64encode(random.randbytes(32)))

    @staticmethod
    def serialize_val(val: Any) -> bytes:
        """Serializes any Python object into bytes"""
        return json.dumps(val).encode()

    @staticmethod
    def unserialize_val(val: bytes) -> Any:
        """De-serializes bytes into original Python object"""
        return json.loads(val.decode())

    @classmethod
    def from_existing(
        cls,
        storage: _T,
        /,
        expire_seconds: int = 0,
        passphrase: _SeedType = '',
        *,
        default: None | Callable[[str], Any] = None
    ) -> Self:
        raise NotImplementedError()

    def _expire(self, key: str) -> None:
        """Marks provided ``key`` to be forgotten after provided ``seconds`` """
        raise NotImplementedError(f"{type(self).__name__} does not support expire keys")

    def iter_matching(self, pattern: str) -> Iterator[tuple[str, Any]]:
        """Iterates over (key, value) pairs of keys that match provided pattern"""
        raise NotImplementedError(f"{type(self).__name__} does not matching iteration")

    def customize_key(self, key: str) -> str:
        """Converts key into a different string, by default :python:`"prefix:{}".format`"""
        return f"{self.prefix}{key}"

    @abc.abstractmethod
    def __getitem__(self, key: str) -> Any:
        """Gets value associated to provided ``key``, raising ``KeyError`` if not found"""
        ...

    @abc.abstractmethod
    def __delitem__(self, key: str) -> None:
        """Deletes provided ``key`` from storage, raising ``KeyError`` if not found"""
        ...

    @abc.abstractmethod
    def __setitem__(self, key: str, value: Any) -> None:
        """Sets value associated to provided ``key``, raising ``KeyError`` if exists"""
        ...

    def delete(self, key: str) -> None:
        """Deletes provided ``key`` from storage doing nothing if not found"""
        try:
            del self[key]
        except KeyError:
            pass

    def get(self, key: str) -> Any:
        """Gets value associated to provided ``key``, returning ``None`` if not found"""
        try:
            return self[key]
        except KeyError:
            return self.default(key)

    def set(self, key: str, value: Any) -> None:
        """Sets ``value`` associated to provided ``key`` overwritting if key exists"""
        self.delete(key)
        self[key] = value


class DictRepository(KeyValueRepository[dict]):
    """In-Memory :class:`dict` used as storage"""

    def __init__(
        self,
        storage: Optional[dict[str, bytes]] = None,
        expire_seconds: int = 0,
        passphrase: _SeedType = '',
        *,
        prefix: str = '',
        default: None | Callable[[str], Any] = None
    ):
        super().__init__(storage or dict(), expire_seconds, passphrase, default=default)
        self.expire_storage: dict[str, datetime] = dict()

    def _expire(self, key: str) -> None:
        if self.expire_seconds <= 0:
            return
        self.expire_storage[key] = _now() + timedelta(seconds=self.expire_seconds)

    def iter_matching(self, pattern: str) -> Iterator[tuple[str, Any]]:
        for key, val in self.storage.items():
            if re.match(pattern, key):
                yield key, val

    def __getitem__(self, key: str) -> Any:
        value = self.storage.get(key)
        if (value is None):
            raise KeyError(f"Key '{key}' not found")
        if (
            (self.expire_seconds > 0)
            and ((ttl := self.expire_storage.get(key)) is not None)
            and (ttl < _now())
        ):
            del self[key]
            raise KeyError(f"Key '{key}' has expired")
        self._expire(key)
        return value

    def __delitem__(self, key: str) -> None:
        try:
            del self.storage[key]
        except KeyError:
            raise KeyError(f"Key '{key}' not found")
        self.expire_storage.pop(key, None)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.storage:
            raise KeyError(f"Key '{key}' already stored")
        self.storage[key] = value
        self._expire(key)


class RedisRepository(KeyValueRepository['Redis']):
    R"""Redis service used as storage

    - Keys can be modified with ``prefix``, customizing
      :method:`KeyValueRepository.customize_key` or customizing redis client (storage)
    - Values are :mod:`pickle`\ .dumped and loaded, to allow arbitrary Python
      objects
    - Results might not persist when Redis restarts, depending on configuration

    """
    @staticmethod
    def serialize_val(val: Any) -> bytes:
        return pickle.dumps(val)

    @staticmethod
    def unserialize_val(val: bytes) -> Any:
        return pickle.loads(val)

    def _expire(self, key: str) -> None:
        if self.expire_seconds <= 0:
            return
        self.storage.expire(key, time=self.expire_seconds)

    def iter_matching(self, pattern: str) -> Iterator[tuple[str, Any]]:
        yield from self.storage.scan_iter(pattern)

    def __getitem__(self, key: str) -> Any:
        val = self.storage.get(key)
        if val is None:
            raise KeyError(f"Key '{key}' not found")
        self._expire(key)
        return val

    def __delitem__(self, key: str) -> None:
        if self.storage.get(key) is None:
            raise KeyError(f"Key '{key}' not found")
        self.storage.delete(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if self.storage.get(key) is not self.default(key):
            raise KeyError(f"Key '{key}' already stored")
        self.storage[key] = value
        self._expire(key)


class DirectoryRepository(KeyValueRepository[Path]):
    R"""Directory used as storage

    - Keys are hashed to avoid issues with file names.
    - Values are :mod:`pickle`\ .dumped and loaded, to allow arbitrary Python
      objects
    - Results are persisted in local filesystem

    """
    def __init__(
        self,
        directory: Path | str = '',
        expire_seconds: int = 0,
        passphrase: _SeedType = '',
        *,
        prefix: str = '',
        default: None | Callable[[str], Any] = None
    ):
        storage = Path(directory or tempfile.mkdtemp())
        if storage.is_file():
            raise TypeError(f"DirectoryRepository initialized with file path '{storage}'")
        super().__init__(storage, expire_seconds, passphrase, default=default)
        self.storage.mkdir(exist_ok=True, parents=True)
        self.expire_storage = shelve.DbfilenameShelf(tempfile.mktemp())

    def customize_key(self, key: str):
        return f"{self.prefix}{md5(key.encode()).hexdigest()}"

    @staticmethod
    def serialize_val(val: Any) -> bytes:
        return pickle.dumps(val)

    @staticmethod
    def unserialize_val(val: bytes) -> Any:
        return pickle.loads(val)

    def _expire(self, key: str) -> None:
        if self.expire_seconds <= 0:
            return
        self.expire_storage[key] = _now() + timedelta(seconds=self.expire_seconds)

    def __getitem__(self, key: str) -> Any:
        filepath = self.storage / f"{key}.pickle"
        if not filepath.exists():
            raise KeyError(f"Key '{key}' not found")
        if (
            (self.expire_seconds > 0)
            and ((ttl := self.expire_storage.get(key)) is not None)
            and (ttl < _now())
        ):
            del self[key]
            raise KeyError(f"Key '{key}' has expired")
        self._expire(key)
        return filepath.read_bytes()

    def __delitem__(self, key: str) -> None:
        filepath = self.storage / f"{key}.pickle"
        if not filepath.exists():
            raise KeyError(f"Key '{key}' not found")
        filepath.unlink()

    def __setitem__(self, key: str, value: Any) -> None:
        filepath = self.storage / f"{key}.pickle"
        if filepath.exists():
            raise KeyError(f"Key '{key}' already stored")
        self._expire(key)
        filepath.write_bytes(value)


class DbFilenameRepository(KeyValueRepository[shelve.DbfilenameShelf]):
    R"""Db filename used as storage

    - Keys are preserved
    - Values are :mod:`pickle`\ .dumped and loaded, to allow arbitrary Python
      objects
    - Results are persisted in local filesystem
    """
    def __init__(
        self,
        filepath: str | Path = '',
        expire_seconds: int = 0,
        passphrase: _SeedType = '',
        *,
        prefix: str = '',
        default: None | Callable[[str], Any] = None
    ):
        if Path(filepath).is_file():
            raise TypeError(f"DbFilenameRepository initialized with file path '{filepath}'")
        storage = shelve.DbfilenameShelf(filepath or tempfile.mktemp())
        super().__init__(storage, expire_seconds, passphrase, default=default)
        self.expire_storage = shelve.DbfilenameShelf(tempfile.mktemp())

    def _expire(self, key: str) -> None:
        if self.expire_seconds <= 0:
            return
        self.expire_storage[key] = _now() + timedelta(seconds=self.expire_seconds)

    def __getitem__(self, key: str) -> Any:
        value = self.storage.get(key)
        if (value is None):
            raise KeyError(f"Key '{key}' not found")
        if (
            (self.expire_seconds > 0)
            and ((ttl := self.expire_storage.get(key)) is not None)
            and (ttl < _now())
        ):
            del self[key]
            raise KeyError(f"Key '{key}' has expired")
        self._expire(key)
        return value

    def __delitem__(self, key: str) -> None:
        try:
            del self.storage[key]
        except KeyError:
            raise KeyError(f"Key '{key}' not found")
        self.expire_storage.pop(key, None)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.storage:
            raise KeyError(f"Key '{key}' already stored")
        self.storage[key] = value
        self._expire(key)


class DefaultRepository(KeyValueRepository[dict]):
    """Repository that always returns values from ``default``"""

    def __init__(self, *, prefix: str = '', default: Callable[[str | bytes], str | bytes]):
        super().__init__(dict(), expire_seconds=0, prefix=prefix, default=default)

    @staticmethod
    def serialize_val(val: Any) -> bytes:
        return pickle.dumps(val)

    @staticmethod
    def unserialize_val(val: bytes) -> Any:
        return pickle.loads(val)

    def __getitem__(self, key: str) -> Any:
        """Keys are defined when retrieved from the first time"""
        try:
            return self.storage[key]
        except KeyError:
            pass
        self[key] = self.default(key)
        return self[key]

    def __delitem__(self, key: str) -> None:
        self.storage.pop(key, None)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.storage:
            raise KeyError(f"Key '{key}' already stored")
        self.storage[key] = value
