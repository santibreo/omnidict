import shelve
import random
from io import BytesIO
from pickle import Pickler, Unpickler
# Installed
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


SeedType = None | int | float | str | bytes | bytearray


def aes_cipher(seed: SeedType):
    """Creates an AES symmetric cipher"""
    random.seed(seed)
    key, nonce = random.randbytes(AES.block_size), random.randbytes(16)
    return AES.new(key, AES.MODE_EAX, nonce=nonce)


class InvalidEncryptionSeedError(ValueError):
    """Exception raised when provided encryption seed is not **correct**"""


class EncryptShelf(shelve.Shelf):
    """:class:`shelve.Shelf` that stored data encrypted using AES symmetric encryption

    .. warning::
       :attr:`~.cache` (used when ``writeback=True`` stores raw data **NOT** encrypted

    """

    def __init__(self, *ar, seed: SeedType = 12345, **kw):
        if not ar:
            ar = (dict(),)
        super().__init__(*ar, **kw)
        self.seed = seed

    @property
    def cipher(self):
        """Returns a new instance of this :class:`EncryptShelf`"""
        return aes_cipher(self.seed)

    def update_aes(self, new_seed: SeedType = None):
        """Re-encrypts all values using provided ``new_seed``"""
        if new_seed == self.seed:
            return
        old_seed = self.seed
        for key in self:
            value = self[key]
            self.seed = new_seed
            self[key] = value
            self.seed = old_seed
        self.seed = new_seed

    def __getitem__(self, key):
        """Gets item unencrypting it if necessary"""
        # When key is in cache
        try:
            return self.cache[key]
        except KeyError:
            pass
        # When key is NOT in cache
        cipherbytes = self.dict[key.encode(self.keyencoding)]
        padded_data = self.cipher.decrypt(cipherbytes)
        f = BytesIO(unpad(padded_data, AES.block_size))
        value = Unpickler(f).load()
        if self.writeback:
            self.cache[key] = value
        return value

    def __setitem__(self, key, value):
        """Sets item encrypting it"""
        if self.writeback:
            self.cache[key] = value
        f = BytesIO()
        p = Pickler(f, self._protocol)
        p.dump(value)
        padded_data = pad(f.getvalue(), AES.block_size)
        self.dict[key.encode(self.keyencoding)] = self.cipher.encrypt(padded_data)


class DbfilenameEncryptShelf(EncryptShelf, shelve.DbfilenameShelf):

    def __init__(self, filename, *ar, seed: SeedType = 12345, **kw):
        super(DbfilenameEncryptShelf, self).__init__(filename, *ar, **kw)
        self.seed = seed
        self.filename = filename
        key = next((k for k in self), None)
        if key is not None:
            # Check encryption key matches original one
            try:
                _ = self[key]
            except ValueError:
                raise InvalidEncryptionSeedError(
                    f"Provided seed {seed!r} does not match original seed used to "
                    f"create dbm file '{filename}'"
                )


