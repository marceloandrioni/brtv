"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = [
    "ValidatorsInStandardOrder",
    "ValidatorsInUserOrder",
    "set_type_annotations_and_validation",
    "set_validate_types_in_func_call",
    "validate_type",
    "validate_types_in_func_call",
]

from abc import ABC, abstractmethod
from collections.abc import (
    Callable,
    Iterable,
)
from functools import wraps
from typing import (
    Any,
)

from multidict import MultiDict
from pydantic import (
    AfterValidator,
    ConfigDict,
    TypeAdapter,
    validate_call,
)

# Notes:
# * Pydantic is permissive with type coercion (e.g., float "2.2" becomes 2.2),
#   so we use strict mode and selectively relax it (e.g., allow int 2.0 -> 2)
#   using custom validators where needed.
# * Arbitrary_types_allowed is needed for numpy, pandas, xarray, etc.
CONFIG = ConfigDict(
    strict=True,
    arbitrary_types_allowed=True,
)


validate_types_in_func_call = validate_call(
    config={
        **CONFIG,
        "validate_default": True,
    },
    validate_return=True,
)


validate_types_in_func_call.__doc__ = (
    """Decorator to enforce type validation on function arguments and return values.

    Examples
    --------
    >>> @validate_types_in_func_call
    ... def my_func(x: int, y: str) -> tuple[int, str]:
    ...     return x, y

    >>> my_func(1, "abc")
    (1, 'abc')

    >>> my_func(1, 2)
      Input should be a valid string [type=string_type, input_value=2,
    input_type=int]

    """
)


def set_validate_types_in_func_call(funcs: Iterable[Callable]) -> None:
    """Set the validate_types_in_func_call decorator to multiple functions.

    Parameters
    ----------
    funcs : Iterable[Callable]
        List of functions to decorate.

    """
    for func in funcs:
        decorated_func = validate_types_in_func_call(func)
        globals()[func.__name__] = decorated_func


def set_type_annotations_and_validation(
    func: Callable,
    annotations: dict[str, Any],
) -> Callable:
    """Add type annotation and validation to a function args/kwargs.

    Parameters
    ----------
    func : Callable
        Function.
    annotations : dict[str, Any]
        Dictionary of argument names and their types. Use "return" to annotate
        the return value.

    Returns
    -------
    func : Callable

    Examples
    --------
    >>> def my_func(x, y):
    ...     return x + y
    >>> my_func = set_type_annotations_and_validation(
    ...     my_func,
    ...     {"x": float, "y": float, "return": float},
    ... )
    >>> my_func(1, "a")
    ValidationError: 1 validation error for my_func
    1
    Input should be a valid number [type=float_type, input_value='a',
    input_type=str]

    """
    for arg_name, arg_type in annotations.items():
        func.__annotations__[arg_name] = arg_type
    return validate_types_in_func_call(func)


def validate_type(
    value: Any,
    type: Any = Any,
    strict: bool | None = None,
    ) -> Any:
    """Validate type.

    Parameters
    ----------
    value : Any
        Value.
    type : Any
        Type of value.
    strict : bool, optional
        Overwrite default strictness.

    Returns
    -------
    value : Any
        Value with type `type`.

    Examples
    --------
    >>> validate_type(1, int)
    1

    >>> validate_type(1.0, int)
      Input should be a valid integer [type=int_type, input_value=1.0,
    input_type=float]

    >>> validate_type(1.0, Union[int, float])
    1.0

    """
    return TypeAdapter(type, config=CONFIG).validate_python(value, strict=strict)


class ValidatorsInStandardOrder:
    """Abstract base class for type validation with standard defined validator order."""

    @classmethod
    def _get_after_validators(cls, validators_args: dict[str, Any]) -> list[Callable]:

        after_validators = []
        for key, value in validators_args.items():
            if value is not None:
                after_validators.append(
                    AfterValidator(getattr(cls, f"make_validator_{key}")(value))
                )

        return after_validators


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


class ValidatorsInUserOrder(ABC):
    """Abstract base class for type validation with user-defined validator order.

    The `__new__` method should only define the function signature and must be
    decorated with `@_call_real_new`. The actual creation of the `Annotated` type
    and application of validators should be implemented in the `_real_new` method.

    This approach preserves the order of validators as specified by the user,
    since Python's argument binding loses the original keyword argument order.
    By passing a MultiDict to `_real_new`, the user-specified order is maintained.

    """

    @abstractmethod
    def _real_new(cls, config: MultiDict):
        pass

    @classmethod
    @abstractmethod
    def _get_after_validators_keys(cls) -> list[str]:
        pass

    @classmethod
    def _get_after_validators(
        cls,
        config: MultiDict,
    ) -> list[Callable]:

        after_validators_all = {
            k: getattr(cls, f"make_validator_{k}")
            for k in cls._get_after_validators_keys()
        }

        after_validators = []
        for key, value in config.items():
            try:
                func = AfterValidator(after_validators_all[key](value))
                after_validators.append(func)
            except KeyError as err:
                err_msg = f"{cls.__name__}() got got an unexpected keyword argument '{key}'."
                raise TypeError(err_msg) from err

        return after_validators
