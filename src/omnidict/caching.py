# Builtins
from functools import wraps
from itertools import starmap
# Local
from omnidict import repositories
# Types
from typing import Any
from typing import Generic
from typing import TypeVar
from typing import Optional
from typing import Callable
from typing import ParamSpec
from typing import Concatenate


_T = TypeVar('_T')
_R = TypeVar('_R', bound=repositories.KeyValueRepository)
_P = ParamSpec('_P')


class Cache(Generic[_R]):
    """Decorator class to cache function calls

    It can be instantiated with a method to validate results. Decorated function
    is called and if it returns a valid value, it is cached.

    You set ``repository`` attribute to define how cache should be stored. Default
    it uses in memory dictionary.

    When you use ``Cache`` instance to decorate a function, the keyword-only
    ``ignore_cache`` argument is added to its signature so you can avoid using
    cached values
    """
    fun_sep = ':?:'
    type_sep = ':&:'
    param_sep = ':::'

    def __init__(
        self,
        repository: Optional[_R] = None,
        result_validator: Optional[Callable[[Any], bool]] = None,
    ):
        if result_validator is not None:
            self.validate = result_validator
        else:
            self.validate = lambda _: True
        if repository is None:
            self.repository: _R = repositories.DictRepository()
        else:
            self.repository: _R = repository

    @classmethod
    def key_from_function_call(cls, func: Callable, *args, **kwargs) -> str:
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

    def __call__(
        self,
        func: Callable[_P, _T]
    ) -> Callable[Concatenate[bool, _P], _T]:

        @wraps(func)
        def inner_func(
            *args: _P.args, ignore_cache: bool = False, **kwargs: _P.kwargs
        ) -> _T:
            try:
                cache_key = self.key_from_function_call(func, *args, **kwargs)
            except IndexError:
                raise TypeError(
                    f"Cannot create cache key for called {func} with {args=} "
                    f"and {kwargs=}"
                )
            # Retrieve key from cache
            if not ignore_cache:
                # Scan cache using None as default
                old_default = self.repository.default
                self.repository.default = lambda _: None
                result = self.repository.get(cache_key)
                self.repository.default = old_default
                if result is not None:
                    return result
            # Retrieve key calling function
            result = func(*args, **kwargs)
            if self.validate(result):
                self.repository.set(cache_key, result)
            return result

        return inner_func
