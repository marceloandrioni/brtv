"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = [
    "BaseLike",
    "BaseLikeInUserOrder",
    "popall_get_last",
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
    Annotated,
    Any,
    get_args,
    get_origin,
    get_type_hints,
)

from multidict import MultiDict
from pydantic import (
    AfterValidator,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    validate_call,
)
from pydantic_core import InitErrorDetails

# Notes:
# * Pydantic is permissive with type coercion (e.g., float "2.2" becomes 2.2),
#   so we use strict mode and selectively relax it (e.g., allow int 2.0 -> 2)
#   using custom validators where needed.
# * Arbitrary_types_allowed is needed for numpy, pandas, xarray, etc.
CONFIG = ConfigDict(
    strict=True,
    arbitrary_types_allowed=True,
    validate_default=True,
)


# validate_types_in_func_call = validate_call(
#     config=CONFIG,
#     validate_return=True,
# )


def validate_types_in_func_call(
        func: Callable,
        strict: bool | None = None,
    ):
    """Wrapper around pydantic.validate_call that prefixes each validation error
    with the field title and description (if present) inside the raised ValidationError."""

    if strict is None:
        config = CONFIG
    else:
        config = ConfigDict(**(CONFIG | {"strict": strict}))

    validated_func = validate_call(func, config=config, validate_return=True)
    hints = get_type_hints(func, include_extras=True)

    def _get_extras(arg_name: str | None):

        title = None
        description = None
        examples = None

        if not arg_name:
            return title, description, examples

        ann = hints.get(arg_name)
        if ann and get_origin(ann) is Annotated:
            _, *extras = get_args(ann)
            for ex in extras:
                title = getattr(ex, "title", None)
                description = getattr(ex, "description", None)
                examples = getattr(ex, "examples", None)

        return title, description, examples

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return validated_func(*args, **kwargs)

        except ValidationError as err:
            rebuilt: list[InitErrorDetails] = []

            for e in err.errors():
                loc = e.get("loc", ())
                typ = e.get("type", "value_error")
                inp = e.get("input", None)
                ctx = dict(e.get("ctx") or {})
                msg = e.get("msg", "")

                # In validate_call errors, loc typically starts with the argument name
                arg = loc[0] if loc else None
                title, description, examples = _get_extras(arg)

                extra_msg = f"\nerror type: {typ}\n"
                extra_msg += f"field title: {title}\n" if title else ""
                extra_msg += f"field description: {description}\n" if description else ""
                extra_msg += f"field examples: {examples}\n" if examples else ""

                # IMPORTANT:
                # We can’t directly set "msg" in InitErrorDetails; pydantic-core builds it.
                # But many built-in errors include ctx and format the message from it.
                #
                # A reliable way is to move our final text into ctx["error"] and use a
                # generic error type that renders ctx["error"].
                #
                # We'll switch to a generic "value_error" and store our full message in ctx.
                full = extra_msg + msg
                ctx["error"] = full

                rebuilt.append(
                    InitErrorDetails(
                        type="value_error",   # force generic so our ctx["error"] is shown
                        loc=loc,
                        input=inp,
                        ctx=ctx,
                    ),
                )

            raise ValidationError.from_exception_data(
                title=getattr(err, "title", func.__name__),
                line_errors=rebuilt,
            ) from None

    return wrapper


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

    # return TypeAdapter(type, config=CONFIG).validate_python(value, strict=strict)

    def func(value: type = value):
        return value
    func.__annotations__["value"] = type

    return validate_types_in_func_call(func, strict=strict)()


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

    @abstractmethod
    def _real_new(cls, config: MultiDict):
        pass


@validate_types_in_func_call
def popall_get_last(md: MultiDict, key: Any, default: Any = None) -> Any:
    """Pop all values from the MultiDict for the given key and return the last one, or default if not found."""
    x = md.popall(key, None)
    if x is None:
        return default
    return x[-1]
