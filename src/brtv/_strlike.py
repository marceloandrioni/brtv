"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = ["StrLike"]

import re
import unicodedata
from collections.abc import Callable, Iterable
from re import Pattern
from typing import Any

from multidict import MultiDict

from ._common import (
    BaseLikeInUserOrder,
    _call_real_new,
    popall_get_last,
    validate_types_in_func_call,
)


class StrLike(BaseLikeInUserOrder):
    """Create a StrLike type for validating string values with customizable constraints.

    Validators are applied in the user requested order.

    Parameters
    ----------
    title : str, optional
        Human-readable title. Useful for documentation and debugging.
    description : str, optional
        Human-readable description. Useful for documentation and debugging.
    examples : list[Any], optional
        Examples of valid values. Useful for documentation and debugging.
    none_to_empty : bool, optional
        Coerce None to empty string.
    strip : bool, optional
        Whether to remove leading and trailing whitespace.
    to_upper : bool, optional
        Whether to convert the string to uppercase.
    to_lower : bool, optional
        Whether to convert the string to lowercase.
    replace : tuple[str, str], optional
        If given a tuple `(pattern, repl)`, replace `pattern` with `repl`.
        Useful when used with the negation modifier (^) to replace all except
        the given pattern, e.g.: `replace=(r"[^a-zA-Z0-9._-]", "_")` replaces
        everything except a-z, A-Z, 0-9, dot (.), underline(_) and hyphen (-)
        with underline.
    remove_accents : bool, optional
        Remove accents replacing accented characters with non-accented ones,
        e.g.: "a ação" -> "a acao"
    startswith : str, optional
        Raises an error if string does not start with the given value.
    endswith : str, optional
        Raises an error if string does not end with the given value.
    pattern : str, Pattern[str], optional
        A regex pattern to validate the string against. An error is raised if
        the string does not match, e.g.: `pattern=r"^[a-zA-Z0-9._ -]*$")` will
        match a string with 0 or more (replace * with + to match 1 or more)
        alphanumeric characters (a to z, A to Z, 0 to 9), dot (.),
        underline (_), space ( ) and hyphen (-). If present, hyphen must be the
        last character, as it can also be used to indicate range (a-z).
    min_length : int, optional
        The minimum length of the string.
    max_length : int, optional
        The maximum length of the string.
    config : Iterable[tuple[str, Any]], optional
        Alternative way of providing the validators in order, as a list of
        (key, value) pairs. This has the advantage of allowing a validator
        to be applied multiple times. If `config` is used, no other kwarg
        is allowed.

    Returns
    -------
    Annotated
        An annotated str type with the specified validation constraints applied.

    Examples
    --------
    >>> validate_type(
    ...     "foobar",
    ...     StrLike(endswith="bar", to_upper=True),
    ... )
    'FOOBAR'

    >>> validate_type(
    ...     "foobar",
    ...     StrLike(config=[("replace", ("foo", "Foo123")), ("replace", ("bar", "Bar456"))]),
    ... )
    'Foo123Bar456'

    >>> @validate_types_in_func_call
    ... def print_hello(separator: StrLike(none_to_empty=True) = None) -> str:
    ...     return f"Hello{separator}World"
    >>> print_hello()
    'HelloWorld'

    """

    @classmethod
    @validate_types_in_func_call
    def make_validator_none_to_empty(
        cls,
        none_to_empty: bool,
    ) -> Callable[[str], str]:

        def validator(value: Any) -> str:
            if none_to_empty and value is None:
                return ""
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_strip(cls, strip: bool) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if strip:
                return value.strip()
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_to_upper(cls, to_upper: bool) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if to_upper:
                return value.upper()
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_to_lower(cls, to_lower: bool) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if to_lower:
                return value.lower()
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_replace(
        cls,
        replace: tuple[str, str],
    ) -> Callable[[str], str]:

        def validator(value: str) -> str:
            return re.sub(*replace, value)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_remove_accents(
        cls,
        remove_accents: bool,
    ) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if remove_accents:
                # https://stackoverflow.com/a/517974
                # Note: another option would be to use unidecode, but unicodedata
                # is a default python lib
                nfkd_form = unicodedata.normalize('NFKD', value)
                return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_startswith(cls, startswith: str) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if value.startswith(startswith):
                return value
            err_msg = f"String does not start with: '{startswith}'"
            raise ValueError(err_msg)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_endswith(cls, endswith: str) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if value.endswith(endswith):
                return value
            err_msg = f"String does not end with: '{endswith}'"
            raise ValueError(err_msg)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_pattern(
        cls,
        pattern: str | Pattern[str],
    ) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if re.match(pattern, value):
                return value
            err_msg = f"String does not match pattern: '{pattern}'"
            raise ValueError(err_msg)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_min_length(cls, min_length: int) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if len(value) < min_length:
                err_msg = f"String length must be at least {min_length}"
                raise ValueError(err_msg)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_max_length(cls, max_length: int) -> Callable[[str], str]:

        def validator(value: str) -> str:
            if len(value) > max_length:
                err_msg = f"String length must be at most {max_length}"
                raise ValueError(err_msg)
            return value

        return validator

    @_call_real_new
    def __new__(
        cls,
        *,
        title: str | None = None,
        description: str | None = None,
        examples: list[Any] | None = None,
        none_to_empty: bool | None = False,
        strip: bool | None = None,
        to_upper: bool | None = None,
        to_lower: bool | None = None,
        replace: tuple[str, str] | None = None,
        remove_accents: bool | None = None,
        startswith: str | None = None,
        endswith: str | None = None,
        pattern: str | Pattern[str] | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        config: Iterable[tuple[str, Any]] | None = None,
    ):
        pass

    @classmethod
    def _real_new(cls, config: MultiDict):

        # Note: most of these validators could be called directly from
        # StringConstraints, but since we want to allow users to specify the
        # order of application, we need to reimplement them here.

        before_validators_args = {
            "none_to_empty": popall_get_last(config, "none_to_empty", False),
        }

        field_validators_args = {
            "title": popall_get_last(config, "title"),
            "description": popall_get_last(config, "description"),
            "examples": popall_get_last(config, "examples"),
            "strict": False,  # allow bytes, StrEnum
        }

        return cls._get_annotated(
            type=str,
            before_validators_args=before_validators_args,
            field_validators_args=field_validators_args,
            after_validators_args=config,
        )
