"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = ["IntLike"]

import numbers
from collections.abc import Callable
from typing import Any

from ._common import (
    BaseLike,
    validate_types_in_func_call,
)


class IntLike(BaseLike):
    """Create an IntLike type for validating integer values with customizable constraints.

    Rounded non-int values (e.g.: `2.0`, `Decimal("2.0")`, `np.array(2.0)`,
    `pd.Series([2.0])`, etc), will be coerced to int.

    Parameters
    ----------
    title : str, optional
        Human-readable title. Useful for documentation and debugging.
    description : str, optional
        Human-readable description. Useful for documentation and debugging.
    examples : list[Any], optional
        Examples of valid values. Useful for documentation and debugging.
    gt : float, optional
        Greater than. If set, value must be greater than this.
    ge : float, optional
        Greater than or equal. If set, value must be greater than or equal to this.
    lt : float, optional
        Less than. If set, value must be less than this.
    le : float, optional
        Less than or equal. If set, value must be less than or equal to this.
    multiple_of : float, optional
        Value must be a multiple of this.

    Returns
    -------
    Annotated
        An annotated int type with the specified validation constraints applied.

    Examples
    --------
    >>> validate_type(
    ...     2.0,
    ...     IntLike(gt=1, lt=3),
    ... )
    2

    >>> @validate_types_in_func_call
    ... def degrees_to_radians(direction: IntLike(ge=0, lt=360)) -> float:
    ...     return np.deg2rad(direction).item()

    """

    @classmethod
    @validate_types_in_func_call
    def make_validator_is_number(cls, is_number: bool) -> Callable[[Any], Any]:

        def validator(value: Any) -> Any:

            if not is_number:
                return value

            # int, float, Decimal, etc
            if isinstance(value, numbers.Number):
                return value

            # numpy ndarray, pandas Series, xarray DataArray, etc
            # will raise if size > 1
            if callable(getattr(value, "item", None)):
                return value.item()

            err_msg = f"Value must be a number, but got '{type(value).__name__}'."
            raise ValueError(err_msg)

        return validator

    @validate_types_in_func_call
    def __new__(
        cls,
        *,
        title: str | None = None,
        description: str | None = None,
        examples: list[Any] | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        multiple_of: float | None = None,
    ):

        before_validators_args = {
            "is_number": True,
        }

        field_validators_args = {
            "title": title,
            "description": description,
            "examples": examples,
            "strict": False,  # allow all but restrict it with is_number_validator
            "gt": gt,
            "ge": ge,
            "lt": lt,
            "le": le,
            "multiple_of": multiple_of,
        }

        return cls._get_annotated(
            type=int,
            before_validators_args=before_validators_args,
            field_validators_args=field_validators_args,
        )
