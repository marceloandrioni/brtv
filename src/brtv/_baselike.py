"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = [
    "BaseLike",
    "BaseLikeInUserOrder",
]

from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import (
    Annotated,
    Any,
)

from multidict import MultiDict
from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
)

from ._common import validate_types_in_func_call


class BaseLike:

    @classmethod
    def _get_validator(cls, key: str, value: Any) -> Callable:
        try:
            func = getattr(cls, f"make_validator_{key}")
        except AttributeError as err:
            err_msg = f"{cls.__name__}() got an unexpected keyword argument '{key}'."
            raise TypeError(err_msg) from err
        validator = func(value)
        return validator

    @classmethod
    def _get_validators(
        cls,
        validators_args: dict[str, Any] | MultiDict,
    ) -> list[Callable]:
        validators = []
        for key, value in validators_args.items():
            if value is None:
                continue
            validators.append(cls._get_validator(key, value))
        return validators

    @classmethod
    def _get_before_validators(
        cls,
        validators_args: dict[str, Any] | MultiDict,
    ) -> list[Callable]:
        return [
            BeforeValidator(validator)
            for validator in cls._get_validators(validators_args)
        ][::-1] # pydantic applies BeforeValidators in reversed order of declaration

    @classmethod
    def _get_after_validators(
        cls,
        validators_args: dict[str, Any] | MultiDict,
    ) -> list[Callable]:
        return [
            AfterValidator(validator)
            for validator in cls._get_validators(validators_args)
        ]

    @classmethod
    def _get_annotated(
        cls,
        *,
        type: Any,
        before_validators_args: dict[str, Any] | MultiDict | None = None,
        field_validators_args: dict[str, Any] | MultiDict | None = None,
        after_validators_args: dict[str, Any] | MultiDict | None = None,
    ):

        args = [type]

        # Annotated must be instantiated at least with Annotated[type, Field()]
        if field_validators_args is not None:
            args += [Field(**field_validators_args)]
        else:
            args += [Field()]

        if before_validators_args is not None:
            args += cls._get_before_validators(before_validators_args)

        if after_validators_args is not None:
            args += cls._get_after_validators(after_validators_args)

        return Annotated[*args]


def _call_real_new(func: Callable) -> Callable:
    """Decorate the `__new__` method so that the `_real_new` is actually called.

    Useful to preserve the method signature of `__new__` while allowing
    custom object creation logic in `_real_new`, including keeping the
    user requested order of keyword arguments.

    Returns
    -------
    Callable
        Wrapped class __new__ method.

    Examples
    --------
    >>> class Foo:
    ...
    ...     @_call_real_new
    ...     def __new__(cls, *, x: float, y: float):
    ...         pass
    ...
    ...     @classmethod
    ...     def _real_new(cls, config: MultiDict) -> dict[str, float]:
    ...         return {k: v * 2 for k, v in config.items()}

    >>> Foo(x=1, y=2)
    {'x': 2, 'y': 4}

    >>> Foo(y=2, x=1)
    {'y': 4, 'x': 2}

    """

    # Note: The goal is to use __new__ to provide a clear method signature, while
    # the actual implementation is handled by _real_new, which uses a dict to
    # preserve the user requested order of validators.
    # This is necessary because python binds the args/kwargs in the signature
    # order (as can be seen with inspect.signature) before executing the function,
    # losing the original order provided by the user.

    # Note: It may be necessary to apply the "same" validator multiple times, but the
    # usual syntax
    #
    # PathLike(
    #   endswith=".csv",
    #   create_as_file=True,  # create empty csv file
    #   with_suffix=".log",
    #   create_as_file=True,  # create empty log file
    # )
    #
    # would fail with "SyntaxError: keyword argument repeated: create_as_file".
    # One way of solving this is to accept a list of (key, value) pairs in
    # the 'config' kwarg and convert it to a multidict.MultiDict, that is
    # basically a dict that allows repeated keys, e.g.:
    #
    # PathLike(
    #     config=[
    #         ("endswith", ".csv"),
    #         ("create_as_file", True),
    #         ("with_suffix", ".log"),
    #         ("create_as_file", True),
    #     ]
    # )

    @wraps(func)
    def wrapper(*args, **kwargs):

        if len(args) > 1:
            err_msg = "Only keyword arguments are allowed."
            raise TypeError(err_msg)
        cls = args[0]

        if "config" in kwargs:
            if set(kwargs) != {"config"}:
                err_msg = "If 'config' is used, no other kwarg is allowed."
                raise TypeError(err_msg)
            config = MultiDict(kwargs["config"])
        else:
            config = MultiDict(kwargs)

        return cls._real_new(config)

    return wrapper


class BaseLikeInUserOrder(BaseLike, ABC):
    """Abstract base class for type validation with user-defined validator order.

    The `__new__` method should only define the function signature and must be
    decorated with `@_call_real_new`. The actual creation of the `Annotated` type
    and application of validators should be implemented in the `_real_new` method.

    This approach preserves the order of validators as specified by the user,
    since Python's argument binding loses the original keyword argument order.
    By passing a MultiDict to `_real_new`, the user-specified order is maintained.

    """

    @staticmethod
    def _call_real_new(func: Callable) -> Callable:
        """Decorate the `__new__` method so that the `_real_new` is actually called.

        Useful to preserve the method signature of `__new__` while allowing
        custom object creation logic in `_real_new`, including keeping the
        user requested order of keyword arguments.

        Returns
        -------
        Callable
            Wrapped class __new__ method.

        Examples
        --------
        >>> class Foo(BaseLikeInUserOrder):
        ...
        ...     @BaseLikeInUserOrder._call_real_new
        ...     def __new__(cls, *, x: float, y: float):
        ...         pass
        ...
        ...     @classmethod
        ...     def _real_new(cls, config: MultiDict) -> dict[str, float]:
        ...         return {k: v * 2 for k, v in config.items()}

        >>> Foo(x=1, y=2)
        {'x': 2, 'y': 4}

        >>> Foo(y=2, x=1)
        {'y': 4, 'x': 2}

        """

        # Note: The goal is to use __new__ to provide a clear method signature, while
        # the actual implementation is handled by _real_new, which uses a dict to
        # preserve the user requested order of validators.
        # This is necessary because python binds the args/kwargs in the signature
        # order (as can be seen with inspect.signature) before executing the function,
        # losing the original order provided by the user.

        # Note: Even inheriting from BaseLikeInUserOrder we still need to use the
        # syntax @BaseLikeInUserOrder._call_real_new instead of simply @_call_real_new
        # because the decorator is resolved like a normal name in the class body,
        # and bare names aren't looked up through the MRO during class body execution.

        # Note: It may be necessary to apply the "same" validator multiple times, but the
        # usual syntax
        #
        # PathLike(
        #   endswith=".csv",
        #   create_as_file=True,  # create empty csv file
        #   with_suffix=".log",
        #   create_as_file=True,  # create empty log file
        # )
        #
        # would fail with "SyntaxError: keyword argument repeated: create_as_file".
        # One way of solving this is to accept a list of (key, value) pairs in
        # the 'config' kwarg and convert it to a multidict.MultiDict, that is
        # basically a dict that allows repeated keys, e.g.:
        #
        # PathLike(
        #     config=[
        #         ("endswith", ".csv"),
        #         ("create_as_file", True),
        #         ("with_suffix", ".log"),
        #         ("create_as_file", True),
        #     ]
        # )

        @wraps(func)
        def wrapper(*args, **kwargs):

            if len(args) > 1:
                err_msg = "Only keyword arguments are allowed."
                raise TypeError(err_msg)
            cls = args[0]

            if "config" in kwargs:
                if set(kwargs) != {"config"}:
                    err_msg = "If 'config' is used, no other kwarg is allowed."
                    raise TypeError(err_msg)
                config = MultiDict(kwargs["config"])
            else:
                config = MultiDict(kwargs)

            return cls._real_new(config)

        return wrapper

    @abstractmethod
    def _real_new(cls, config: MultiDict):
        pass

    @staticmethod
    @validate_types_in_func_call
    def _popall_get_last(md: MultiDict, key: Any, default: Any = None) -> Any:
        """Pop all values from the MultiDict for the given key and return the last one, or default if not found."""
        x = md.popall(key, None)
        if x is None:
            return default
        return x[-1]
