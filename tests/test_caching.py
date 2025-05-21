from unittest import mock
from unittest import TestCase
from collections import defaultdict
import pytest
from omnidict import caching
from omnidict import repositories


cache = caching.Cache(repositories.DictRepository(expire_seconds=60))
class Case(TestCase):

    call_counter: dict[str, int] = defaultdict(int)

    @staticmethod
    def f(a, b, /, c, d, *, e, f) -> int:
        Case.call_counter['f'] += 1
        return 0

    def m(self, a, /, b, *, c) -> int:
        Case.call_counter['m'] += 1
        return 0

    @staticmethod
    @cache
    def cf(a, b, /, c, d, *, e, f) -> int:
        Case.call_counter['cf'] += 1
        return 0

    @cache
    def cm(self, a, /, b, *, c) -> int:
        Case.call_counter['cm'] += 1
        return 0


case = Case()


def test_key_from_function_call():

    def tester(func):

        def inner(*args, **kwargs):
            return caching.Cache.key_from_function_call(func, *args, **kwargs)

        return inner

    key_1 = tester(case.f)(1, 2, c=3, d=4, e=5, f=6)
    case.assertEqual(key_1, "test_caching.f:?:1:::2:&:f=6:::e=5:::d=4:::c=3")
    key_2 = tester(case.f)(1, 2, 3, e=5, f=6, d=4)
    case.assertEqual(key_1, key_2, "Equivalent function calls are different")
    key_3 = tester(case.m)(1, c=3, b=2)
    case.assertEqual(key_3, 'test_caching.m:?:1:&:c=3:::b=2')


def test_funcion_call_from_key():
    key_1 = "test_caching.f:?:1:::2:&:f=6:::e=5:::d=4:::c=3"
    _, args_1, kwargs_1 = caching.Cache.function_call_from_key(key_1)
    case.assertTupleEqual(args_1, ('1', '2'))
    case.assertDictEqual(kwargs_1, {'f': '6', 'e': '5', 'd': '4', 'c': '3'})
    key_3 = 'test_caching.m:?:1:&:c=3:::b=2'
    _, args_3, kwargs_3 = caching.Cache.function_call_from_key(key_3)
    case.assertTupleEqual(args_3, ('1',))
    case.assertDictEqual(kwargs_3, {'c': '3', 'b': '2'})


@pytest.mark.parametrize('call, call_key', [
    (lambda: case.cf(1, 2, 3, 4, e=5, f=6), 'cf'),
    (lambda: case.cm(1, 2, c=3), 'cm'),
])
def test_cache_calls_function_when_not_found(call, call_key):
    prev_counter = case.call_counter[call_key]
    result = call()
    assert result == 0, 'Result differs from expected'
    assert (prev_counter + 1) == case.call_counter['cf'], 'Cached method not called'


@pytest.mark.parametrize('call_a, call_b, call_key', [
    (lambda: case.cf(1, 2, 3, 4, e=5, f=6), lambda: case.cf(1, 2, c=3, d=4, e=5, f=6), 'cf'),
    (lambda: case.cm(1, 2, c=3), lambda: case.cm(1, b=2, c=3), 'cm'),
])
def test_cache_does_not_call_function_when_found(call_a, call_b, call_key):
    result = call_a()
    prev_counter = case.call_counter[call_key]
    result = call_b()
    assert result == 0, 'Result differs from expected'
    assert prev_counter == case.call_counter[call_key], 'Cached method called'


@pytest.mark.parametrize('call_a, call_b, call_key', [
    (lambda: case.cf(1, 2, 3, 4, e=5, f=6), lambda: case.cf(1, 2, c=3, d=4, e=5, f=6, ignore_cache=True), 'cf'),
    (lambda: case.cm(1, 2, c=3), lambda: case.cm(1, b=2, c=3, ignore_cache=True), 'cm'),
])
def test_cache_calls_function_when_cache_ignored(call_a, call_b, call_key):
    result = call_a()
    prev_counter = case.call_counter[call_key]
    result = call_b()
    assert result == 0, 'Result differs from expected'
    assert (prev_counter + 1) == case.call_counter[call_key], 'Cached method not called'
