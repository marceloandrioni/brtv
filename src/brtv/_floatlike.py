"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = ["FloatLike"]

import math
from decimal import Decimal
from typing import (
    Annotated,
    Any,
)

from pydantic import Field

from ._common import (
    FuncFloatFloat,
    validate_type,
    validate_types_in_func_call,
)
from ._intlike import IntLike


class FloatLike(IntLike):
    """Create a FloatLike type for validating float values with customizable constraints.

    Validators are applied in this order below, regardless of the order in which
    the arguments are provided by the user.

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
    allow_nan : bool, optional
        Allow NaN. Default is False.
    allow_inf : bool, optional
        Allow Inf/-Inf. Default is False.
    max_decimal_places: int, optional
        Maximum number of decimal places allowed. It does not include trailing decimal zeroes.

    Returns
    -------
    Annotated
        An annotated float type with the specified validation constraints applied.

    Examples
    --------
    >>> validate_type(
    ...     2.2,
    ...     FloatLike(gt=1, lt=3),
    ... )
    2

    >>> @validate_types_in_func_call
    ... def degrees_to_radians(direction: FloatLike(ge=0, lt=360)) -> float:
    ...     return np.deg2rad(direction).item()

    """

    @classmethod
    @validate_types_in_func_call
    def make_validator_allow_nan(cls, allow_nan: bool) -> FuncFloatFloat:

        def validator(value: float) -> float:
            if math.isnan(value) and not allow_nan:
                raise ValueError("Value can't be NaN.")
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_allow_inf(cls, allow_inf: bool) -> FuncFloatFloat:

        def validator(value: float) -> float:
            if math.isinf(value) and not allow_inf:
                raise ValueError("Value can't be Inf.")
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_max_decimal_places(
        cls,
        max_decimal_places: int,
    ) -> FuncFloatFloat:

        def validator(value: float) -> float:

            # don't apply decimal places validation to NaN or Inf, since they don't have decimal places
            if not math.isfinite(value):
                return value

            # convert to Decimal and use the existing decimal_places validator
            validate_type(
                Decimal(f"{value}"),
                Annotated[Decimal, Field(decimal_places=max_decimal_places)],
            )

            return value

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
        allow_nan: bool = False,
        allow_inf: bool = False,
        max_decimal_places: int | None = None,
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

        after_validators_args = {
            "allow_nan": allow_nan,
            "allow_inf": allow_inf,
            "max_decimal_places": max_decimal_places,
        }

        return cls._get_annotated(
            type=float,
            before_validators_args=before_validators_args,
            field_validators_args=field_validators_args,
            after_validators_args=after_validators_args,
        )
