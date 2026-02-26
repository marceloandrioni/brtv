"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = ["ListLike"]

from typing import Any

from pydantic import ValidationError

from ._baselike import BaseLike
from ._common import (
    FuncAnyAny,
    FuncListList,
    validate_type,
    validate_types_in_func_call,
)


class ListLike(BaseLike):
    """Create a ListLike type for validating lists of objects with customizable constraints.

    Validators are applied in this order below, regardless of the order in which
    the arguments are provided by the user.

    Parameters
    ----------
    item_type : Any
        The type of items in the list. It can be a simple type (e.g.: Any, int,
        float, str, another list, etc) or a custom type with its own validation
        (e.g., `FloatLike(gt=0)`).
    title : str, optional
        Human-readable title. Useful for documentation and debugging.
    description : str, optional
        Human-readable description. Useful for documentation and debugging.
    examples : list[Any], optional
        Examples of valid values. Useful for documentation and debugging.
    none_to_empty : bool, optional
        Coerce None to empty list.
    coerce_scalar : bool, optional
        If True, single items that match the item_type will be coerced to
        a list with one item. Useful for allowing both single items and lists of
        items as input. If the input is ambiguous (i.e., it can be successfully
        validated both as a `value` and `list[value]` against `item_type`),
        an error will be raised.
    min_length : int, optional
        Minimum length of items in the list.
    max_length : int, optional
        Maximum length of items in the list.
    length : int, optional
        Exact length of items in the list.
    unique_items : bool, optional
        Raises an error if there are repeated items in the list.
    sorted : bool, optional
        Raises an error if list is not sorted.
    sorted_reverse : bool, optional
        Raises an error if list is not sorted in descending order.
    sort : bool, optional
        Sorts the list in ascending order.
    sort_reverse : bool, optional
        Sorts the list in descending order.

    Returns
    -------
    Annotated
        An annotated list type with the specified validation constraints applied.

    Examples
    --------
    >>> validate_type(
    ...     [2.2, 3, 4.1, 1],
    ...     ListLike(float, min_length=2, unique_items=True, sort=True),
    ... )
    [1.0, 2.2, 3.0, 4.1]

    >>> validate_type(
    ...     2.2,
    ...     ListLike(FloatLike(gt=0), coerce_scalar=True),
    ... )
    [2.2]

    >>> @validate_types_in_func_call
    ... def sum_list(values: ListLike(FloatLike(gt=0), min_length=2)) -> float:
    ...     return sum(values)

    """

    @classmethod
    @validate_types_in_func_call
    def make_validator_none_to_empty(cls, none_to_empty: bool) ->  FuncAnyAny:

        def validator(value: Any) -> Any:
            if none_to_empty and value is None:
                return []
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_coerce_scalar(cls, args: tuple[bool, Any]) -> FuncAnyAny:

        coerce_scalar, item_type = args

        def validator(value: Any) -> Any:
            # Note: can't just check if is iterable because str, list[str],
            # list[list[floats]], etc, are all valid situations. The only way is
            # to actually try validating both as scalar and list.

            if coerce_scalar:

                try:
                    validate_type(value, item_type)
                    valid_as_scalar = True
                except ValidationError:
                    valid_as_scalar = False

                try:
                    validate_type([value], item_type)
                    valid_as_list = True
                except ValidationError:
                    valid_as_list = False

                if valid_as_scalar and valid_as_list:
                    err_msg = (
                        "Can't use `coerce_scalar=True` because the value is ambiguous."
                        " Can be successfully validate both as `value` and `[value]`"
                        f" against type `{item_type}`. Avoid using this option with"
                        " broad type definitions like `Any`, `list[Any]`, etc."
                    )
                    raise ValueError(err_msg)

                if valid_as_scalar:
                    return [value]

            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_iterable_to_list(
        cls,
        iterable_to_list: bool,
        ) -> FuncAnyAny:

        def validator(value: Any) -> Any:
            if iterable_to_list:
                try:
                    return list(value)
                except TypeError as err:
                    err_msg = "Input should be an iterable that can be converted to a list."
                    raise ValueError(err_msg) from err
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_length(cls, length: int) -> FuncListList:

        def validator(value: list[Any]) -> list[Any]:
            if len(value) != length:
                err_msg = f"List must have exactly {length} items."
                raise ValueError(err_msg)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_unique_items(cls, unique_items: bool) -> FuncListList:

        def validator(value: list[Any]) -> list[Any]:
            if unique_items and len(value) != len(set(value)):
                err_msg = "List items must be unique."
                raise ValueError(err_msg)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_is_sorted(cls, is_sorted: bool) -> FuncListList:

        def validator(value: list[Any]) -> list[Any]:
            if is_sorted:
                if sorted(value) == value:
                    return value
                err_msg = "List must be sorted."
                raise ValueError(err_msg)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_is_sorted_reverse(
        cls,
        is_sorted_reverse: bool,
    ) -> FuncListList:

        def validator(value: list[Any]) -> list[Any]:
            if is_sorted_reverse:
                if sorted(value, reverse=True) == value:
                    return value
                err_msg = "List must be sorted in reverse."
                raise ValueError(err_msg)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_sort(cls, sort: bool) -> FuncListList:

        def validator(value: list[Any]) -> list[Any]:
            if sort:
                return sorted(value)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_sort_reverse(cls, sort_reverse: bool) -> FuncListList:

        def validator(value: list[Any]) -> list[Any]:
            if sort_reverse:
                return sorted(value, reverse=True)
            return value

        return validator

    @validate_types_in_func_call
    def __new__(
        cls,
        item_type: Any,
        *,
        title: str | None = None,
        description: str | None = None,
        examples: list[Any] | None = None,
        none_to_empty: bool = False,
        coerce_scalar: bool = False,
        min_length: int | None = None,
        max_length: int | None = None,
        length: int | None = None,
        unique_items: bool | None = None,
        sorted: bool | None = None,
        sorted_reverse: bool | None = None,
        sort: bool | None = None,
        sort_reverse: bool | None = None,
    ):

        before_validators_args = {
            "none_to_empty": none_to_empty,
            "coerce_scalar": (coerce_scalar, item_type),
            "iterable_to_list": True,
        }

        field_validators_args = {
            "title": title,
            "description": description,
            "examples": examples,
            "min_length": min_length,
            "max_length": max_length,
            "fail_fast": True,  # stop at the first error in the list
        }

        after_validators_args = {
            "length": length,
            "unique_items": unique_items,
            "is_sorted": sorted,  # use different key to not shadow the built-in sorted function
            "is_sorted_reverse": sorted_reverse,
            "sort": sort,
            "sort_reverse": sort_reverse,
        }

        return cls._get_annotated(
            type=list[item_type],
            before_validators_args=before_validators_args,
            field_validators_args=field_validators_args,
            after_validators_args=after_validators_args,
        )
