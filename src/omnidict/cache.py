# Builtins
from functools import wraps
from itertools import starmap
# Local
from key_value_storage import storage_tools
# Types
from typing import Any
from typing import Type
from typing import Generic
from typing import TypeVar
from typing import Optional
from typing import Callable
from typing import ParamSpec
from typing import Concatenate


T = TypeVar('T')
P = ParamSpec('P')
ResultValidator = Callable[[Any], bool]
CacheCreator = Callable[[ResultValidator], 'Cache']


class Cache:
    """Decorator class to cache function calls

    It can be instantiated with a method to validate results. Decorated function
    is called and if it returns a valid value, it is cached.

    You set ``storage`` attribute to define how cache should be stored. Default
    is using ``pickle`` files in ``~/.cache/`` directory

    When you use ``Cache`` instance to decorate a function, the keyword-only
    ``ignore_cache`` argument is added to its signature so you can avoid using
    cached values
    """
    fun_sep = ':?:'
    type_sep = ':&:'
    param_sep = ':::'

    def __init__(
        self,
        result_validator: Optional[ResultValidator] = None,
        storage: storage_tools.KeyValueStorage = storage_tools.DirectoryStorage()
    ):
        if result_validator is not None:
            self.validate = result_validator
        else:
            self.validate = lambda _: True


    @classmethod
    def make_function_call_key(cls, func: Callable, *args, **kwargs) -> str:
        """Creates cache key for given function, arguments and keyword
        arguments
        """
        def all_as_kwargs(*args, **kwargs):
            in_args, in_kwargs = list(args), dict()
            npos = func.__code__.co_posonlyargcount
            nargs = func.__code__.co_argcount + func.__code__.co_kwonlyargcount
            varnames = list(func.__code__.co_varnames[:nargs][::-1])
            for i, varname in enumerate(varnames, start=1):
                # Take kwonly args from kwargs
                try:
                    in_kwargs[varname] = kwargs[varname]
                except KeyError:
                    pass
                else:
                    continue
                # Leave remaining args in kwargs
                if (nargs - len(in_kwargs)) == npos:
                    break
                # Move pos args to kwargs when possible
                try:
                    in_kwargs[varname] = in_args.pop(-1)
                except IndexError:
                    pass
            return in_args, in_kwargs

        prefix = f"{func.__module__}.{func.__name__}"
        in_args, in_kwargs = all_as_kwargs(*args, **kwargs)
        argstr = cls.param_sep.join(map(str, in_args))
        kwargstr = cls.param_sep.join(starmap("{}={}".format, in_kwargs.items()))
        return f"{prefix}{cls.fun_sep}{argstr}{cls.type_sep}{kwargstr}"


    @classmethod
    def function_call_from_key(
        cls,
        key: str
    ) -> tuple[str, tuple[str, ...], dict[str, str]]:
        """Recompose function call from cache key.

        .. warning::
            Every argument is returned as a string, this method do not cast
            argument types

        Args:
            key: The key to be decomposed

        Returns:
            Function fully qualified name, call arguments and call keyword
            arguments
        """
        prefix, argstr_and_kwargstr = key.split(cls.fun_sep)
        argstr, kwargstr = argstr_and_kwargstr.split(cls.type_sep)
        args = tuple(map(str, filter(bool, argstr.split(cls.param_sep))))
        kwargs_tuple = tuple(filter(bool, kwargstr.split(cls.param_sep)))
        kwargs = dict(map(lambda s: s.split('=', 1), kwargs_tuple))
        return prefix, args, kwargs

    @property
    def storage(self) -> storage_tools.KeyValueStorage:
        """Gets :class:`storage_tools.KeyValueStorage` with cached results"""
        return type(self)._storage

    @storage.setter
    def storage(self, storage: storage_tools.KeyValueStorage) -> None:
        """Sets :class:`storage_tools.KeyValueStorage` to provided ``storage``"""
        type(self)._storage = storage

    def __call__(
        self,
        func: Callable[P, T]
    ) -> Callable[Concatenate[bool, P], T]:

        @wraps(func)
        def inner_func(
            *args: P.args, ignore_cache: bool = False, **kwargs: P.kwargs
        ) -> T:
            try:
                cache_key = self.make_function_call_key(func, *args, **kwargs)
            except IndexError:
                raise TypeError(
                    f"Cannot create cache key for called {func} with {args=} "
                    f"and {kwargs=}"
                )
            if not ignore_cache:
                result = self.storage.get(cache_key)
                if result is not None and self.validate(result):
                    return result
            self.storage.delete(cache_key)
            result = func(*args, **kwargs)
            if self.validate(result):
                self.storage.set(cache_key, result)
            return result

        return inner_func
