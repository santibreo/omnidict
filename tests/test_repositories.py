from uuid import uuid4
from datetime import datetime, timedelta
import pytest
from fakeredis import FakeRedis
from omnidict import repositories
from typing import Callable
from cryptography.fernet import InvalidToken


DEFAULT_STANDARD_KW = {'expire_seconds': 60}
DEFAULT_ENCRYPTED_KW = {'expire_seconds': 60, 'passphrase': 'test'}


RepositoryFactory = Callable[[...], repositories.KeyValueRepository]



STANDARD_REPOS: list[RepositoryFactory] = [
    lambda **kw: repositories.DictRepository(**(DEFAULT_STANDARD_KW | kw)),
    lambda **kw: repositories.DirectoryRepository(**(DEFAULT_STANDARD_KW | kw)),
    lambda **kw: repositories.DbFilenameRepository(**(DEFAULT_STANDARD_KW | kw)),
    lambda **kw: repositories.RedisRepository(FakeRedis(), **(DEFAULT_STANDARD_KW | kw)),
]
ENCRYPTED_REPOS: list[RepositoryFactory] = [
    lambda **kw: repositories.DictRepository(**(DEFAULT_ENCRYPTED_KW | kw)),
    lambda **kw: repositories.DirectoryRepository(**(DEFAULT_ENCRYPTED_KW | kw)),
    lambda **kw: repositories.DbFilenameRepository(**(DEFAULT_ENCRYPTED_KW | kw)),
    lambda **kw: repositories.RedisRepository(FakeRedis(), **(DEFAULT_ENCRYPTED_KW | kw)),
]
DEFAULT_REPO: list[RepositoryFactory] = [
    lambda **kw: repositories.DefaultRepository(default=lambda _: uuid4(), **kw)
]
ALL_REPOS = STANDARD_REPOS + ENCRYPTED_REPOS + DEFAULT_REPO


@pytest.mark.parametrize('repository_factory', ALL_REPOS)
def test_customize_key(repository_factory: RepositoryFactory):
    repository = repository_factory()
    repository.customize_key = "aaa:{}:bbb".format
    assert repository.customize_key('key').startswith('aaa:'), 'Key not customized'
    assert repository.customize_key('key').endswith(':bbb'), 'Key not customized'


@pytest.mark.parametrize('repository_factory', ALL_REPOS)
def test_customize_key_prefix(repository_factory: RepositoryFactory):
    repository = repository_factory(prefix='testing::')
    assert repository.customize_key('key').startswith('testing::'), 'Key not customized'


@pytest.mark.parametrize('repository_factory', STANDARD_REPOS + ENCRYPTED_REPOS)
def test_get_not_found(repository_factory):
    repository = repository_factory()
    with pytest.raises(KeyError):
        repository['a']


@pytest.mark.parametrize('repository_factory', STANDARD_REPOS + ENCRYPTED_REPOS)
def test_get_not_found_by_method(repository_factory):
    repository = repository_factory()
    assert repository.get('a') is repository.default('a'), '`get` non existing key'


@pytest.mark.parametrize('repository_factory', ALL_REPOS)
def test_get_existing(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'
    assert repository['a'] == '1', '`__getitem__` existing key'


@pytest.mark.parametrize('repository_factory',  ALL_REPOS)
def test_get_existing_by_method(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'
    assert repository.get('a') == '1', '`get` existing key'


@pytest.mark.parametrize('repository_factory', STANDARD_REPOS + ENCRYPTED_REPOS)
def test_del_not_found(repository_factory):
    repository = repository_factory()
    with pytest.raises(KeyError):
        del repository['a']


@pytest.mark.parametrize('repository_factory',  ALL_REPOS)
def test_del_not_found_by_method(repository_factory):
    repository = repository_factory()
    assert repository.delete('a') is None, '`delete` non existing key'


@pytest.mark.parametrize('repository_factory',  ALL_REPOS)
def test_del_existing(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'
    del repository['a']


@pytest.mark.parametrize('repository_factory',  ALL_REPOS)
def test_del_existing_by_method(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'
    assert repository.delete('a') is None, '`delete` existing key'


@pytest.mark.parametrize('repository_factory', ALL_REPOS)
def test_set_not_found(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'


@pytest.mark.parametrize('repository_factory', ALL_REPOS)
def test_set_not_found_by_method(repository_factory):
    repository = repository_factory()
    assert repository.set('a', '1') is None, '`set` non existing key'


@pytest.mark.parametrize('repository_factory',  ALL_REPOS)
def test_set_existing(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'
    with pytest.raises(KeyError):
        repository['a'] = 1


@pytest.mark.parametrize('repository_factory',  ALL_REPOS)
def test_set_existing_by_method(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'
    assert repository.set('a', '1') is None, '`set` existing key'


@pytest.mark.parametrize('repository_factory', STANDARD_REPOS + ENCRYPTED_REPOS)
def test_get_expired_key(repository_factory, freezer):
    repository = repository_factory()
    repository['a'] = '1'
    freezer.move_to(timedelta(seconds=61))
    with pytest.raises(KeyError):
        repository['a']


@pytest.mark.parametrize('repository_factory', STANDARD_REPOS + ENCRYPTED_REPOS)
def test_get_expired_key_by_method(repository_factory, freezer):
    repository = repository_factory()
    repository['a'] = '1'
    freezer.move_to(timedelta(seconds=61))
    assert repository.get('a') == repository.default('a'), 'get expired key is not default'


@pytest.mark.parametrize('repository_factory', STANDARD_REPOS + ENCRYPTED_REPOS)
def test_get_key_refreshes_expiration(repository_factory, freezer):
    repository: repositories.KeyValueRepository = repository_factory()
    start = datetime.now()
    repository['a'] = '1'
    freezer.move_to(timedelta(seconds=40))
    _ = repository.get('a')
    freezer.move_to(timedelta(seconds=40))
    val = repository.get('a')
    assert (datetime.now() - start) > timedelta(seconds=repository.expire_seconds), (
        'Not enough time elapsed'
    )
    assert val == '1', 'get does not refreshes expiration'


@pytest.mark.parametrize('repository_factory', ENCRYPTED_REPOS)
def test_encrypted_values(repository_factory):
    repository = repository_factory()
    repository['a'] = '1'
    repository.cipher = repository.build_cipher('other')
    with pytest.raises(InvalidToken):
        repository.get('a')
