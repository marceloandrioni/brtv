"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = [
    "set_type_annotations_and_validation",
    "set_validate_types_in_func_call",
    "validate_type",
    "validate_types_in_func_call",
]

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

from pydantic import (
    ConfigDict,
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

    config = CONFIG
    if strict is not None:
        config = ConfigDict(**(config | {"strict": strict}))

    validated_func = validate_call(func, config=config, validate_return=True)
    hints = get_type_hints(func, include_extras=True)

    def _get_metadata(arg_name: str, metadata_name: str):

        metadata = None

        ann = hints.get(arg_name)
        if ann and get_origin(ann) is Annotated:
            _, *extras = get_args(ann)
            for ex in extras:
                metadata = getattr(ex, metadata_name, None)

        return metadata

    def _rebuild_error_with_metadata(err):

        loc = err.get("loc", ())
        typ = err.get("type", "value_error")
        inp = err.get("input", None)
        ctx = dict(err.get("ctx") or {})
        msg = err.get("msg", "")
        # In validate_call errors, loc typically starts with the argument name
        arg = loc[0] if loc else None

        title = _get_metadata(arg, "title")
        description = _get_metadata(arg, "description")
        examples = _get_metadata(arg, "examples")

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

        return InitErrorDetails(
            type="value_error",   # force generic so our ctx["error"] is shown
            loc=loc,
            input=inp,
            ctx=ctx,
        )

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return validated_func(*args, **kwargs)

        except ValidationError as err:

            line_errors: list[InitErrorDetails] = [
                _rebuild_error_with_metadata(e)
                for e in err.errors()
            ]

            raise ValidationError.from_exception_data(
                title=getattr(err, "title", func.__name__),
                line_errors=line_errors,
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
        Overwrite default strictness. Useful for testing.

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

    def func(value):
        return value
    func.__annotations__["value"] = type

    return validate_types_in_func_call(func, strict=strict)(value)


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
