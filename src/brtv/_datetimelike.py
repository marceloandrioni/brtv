"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = ["DatetimeLike"]

import datetime
import dateutil
from collections.abc import Iterable
from itertools import accumulate
from typing import Any

import numpy as np
import pandas as pd
from multidict import MultiDict
from pydantic import AwareDatetime, NaiveDatetime

from ._baselike import BaseLikeInUserOrder
from ._common import (
    FuncAnyAny,
    FuncDtDt,
    validate_type,
    validate_types_in_func_call,
)
from ._intlike import IntLike


def get_datetime_formats() -> list[str]:
    """Return a list of valid datetime formats."""

    def add_fz(lst: list[str]) -> list[str]:
        return lst + [f"{lst[-1]}{x}" for x in [".%f", "%z", ".%f%z"]]

    Y_m_d_H_M_S = add_fz(list(accumulate(["%Y", "-%m", "-%d", " %H", ":%M", ":%S"])))
    Y_m_dTH_M_S = add_fz(list(accumulate(["%Y", "-%m", "-%d", "T%H", ":%M", ":%S"])))
    YmdHMS = add_fz(list(accumulate(["%Y", "%m", "%d", "%H", "%M", "%S"])))
    d_m_Y_H_M_S = add_fz(list(accumulate(["%d/%m/%Y", " %H", ":%M", ":%S"])))
    fmts = Y_m_d_H_M_S + Y_m_dTH_M_S + YmdHMS + d_m_Y_H_M_S

    # remove duplicated keeping order
    return list(dict.fromkeys(fmts))


class DatetimeLike(BaseLikeInUserOrder):
    """Create a DatetimeLike type for validating datetime values with customizable constraints.

    Validators are applied in the user requested order.

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
    config : Iterable[tuple[str, Any]], optional
        Alternative way of providing the validators in order, as a list of
        (key, value) pairs. This has the advantage of allowing a validator
        to be applied multiple times. If `config` is used, no other kwarg
        is allowed.

    Returns
    -------
    Annotated
        An annotated Path type with the specified validation constraints applied.

    Examples
    --------
    >>> validate_type("d=01, m=02, y=2003", DatetimeLike(format="d=%d, m=%m, y=%Y"))
    datetime.datetime(2003, 2, 1, 0, 0)

    >>> validate_type(
    ...     "foobar.txt",
    ...     PathLike(absolute=True, endswith=".txt"),
    ... )
    PosixPath('/home/user/foobar.txt')

    >>> validate_type(
    ...     "foobar.txt",
    ...     PathLike(config=[("absolute", True), ("endswith", ".txt")]),
    ... )
    PosixPath('/home/user/foobar.txt')

    useful for reading
    >>> input_file_csv = PathLike(
    ...     title="Input file",
    ...     description="CSV input file",
    ...     endswith=".csv;.CSV",
    ...     exist_as_file=True,
    ...     readable=True,
    ...     absolute=True,
    ... )
    >>> @validate_types_in_func_call
    ... def read_csv(path: input_file_csv) -> pd.DataFrame:
    ...     return pd.read_csv(path)

    useful for writing
    >>> output_file_csv = PathLike(
    ...     title="Output file",
    ...     description="CSV output file",
    ...     endswith=".csv",
    ...     writable=True,
    ...     create_parents=True,
    ...     absolute=True,
    ... )
    >>> @validate_types_in_func_call
    ... def write_csv(df: pd.DataFrame, path: output_file_csv) -> None:
    ...     df.to_csv(path)

    useful for creating related files
    >>> output_file_stats = PathLike(
    ...     endswith=".csv",
    ...     with_suffix=".stats",
    ...     writable=True,
    ...     create_parents=True,
    ...     absolute=True,
    ... )
    >>> @validate_types_in_func_call
    ... def save_stats(df: pd.DataFrame, path: output_file_stats) -> None:
    ...     print(f"Saving stats to '{path}'")
    ...     df.describe().to_csv(path)

    """

    @classmethod
    @validate_types_in_func_call
    def make_validator_date_to_datetime(cls, date_to_datetime: bool) -> FuncAnyAny:

        def validator(value: Any) -> Any:
            # add 00:00 to date
            if date_to_datetime and isinstance(value, datetime.date):
                return datetime.datetime.combine(
                    value,
                    datetime.datetime.min.time(),
                )
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_dt64_to_datetime(cls, dt64_to_datetime: bool) -> FuncAnyAny:

        def validator(value: Any) -> Any:
            # add 00:00 to date
            if dt64_to_datetime and isinstance(value, np.datetime64):
                return pd.to_datetime(value).to_pydatetime()
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_timestamp_to_datetime(
        cls,
        timestamp_to_datetime: bool,
    ) -> FuncAnyAny:

        def validator(value: Any) -> Any:
            # add 00:00 to date
            if timestamp_to_datetime and isinstance(value, pd.Timestamp):
                return value.to_pydatetime()
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_dt_format(cls, dt_format: str) -> FuncAnyAny:

        def validator(value: Any) -> Any:
            if isinstance(value, str):
                return datetime.datetime.strptime(value, dt_format)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_str_to_datetime(cls, str_to_datetime: bool) -> FuncAnyAny:

        def validator(value: Any) -> Any:

            # Note: pydantic parses strings without "-" as seconds/milliseconds, e.g.:
            # >>> TypeAdapter(datetime.datetime).validate_python("20010203")
            # datetime.datetime(1970, 8, 20, 14, 23, 23, tzinfo=TzInfo(UTC))
            # so using a custom list of valid formats

            if str_to_datetime and isinstance(value, str):

                fmts = get_datetime_formats()
                for fmt in fmts:
                    try:
                        return datetime.datetime.strptime(value, fmt)
                    except ValueError as err:
                        pass

                fmts_str = "\n".join([f"'{fmt}'" for fmt in fmts])
                err_msg = (
                    f"String '{value}' is not in a recognized datetime format."
                    f" Valid formats:\n{fmts_str}\n"
                )
                raise ValueError(err_msg)

            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_must_be_naive(cls, must_be_naive: bool) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            if must_be_naive:
                return validate_type(value, NaiveDatetime)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_must_be_aware(cls, must_be_aware: bool) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            if must_be_aware:
                return validate_type(value, AwareDatetime)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_must_be_utc(cls, must_be_utc: bool) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            if must_be_utc:
                cls.make_validator_must_be_aware(True)(value)
                if value.tzinfo.utcoffset(value) != datetime.timedelta(0):
                    err_msg = "Value must be in UTC (with zero offset)."
                    raise ValueError(err_msg)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_naive_to_utc(cls, naive_to_utc: bool) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            if naive_to_utc:
                try:
                    cls.make_validator_must_be_naive(True)(value)
                except ValueError:
                    return value
                return value.replace(tzinfo=datetime.timezone.utc)
            return value

        return validator


    @classmethod
    @validate_types_in_func_call
    def make_validator_naive_to_tz(cls, naive_to_tz: IntLike(ge=-23, le=23)) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            try:
                cls.make_validator_must_be_naive(True)(value)
            except ValueError:
                return value
            tz = datetime.timezone(datetime.timedelta(hours=naive_to_tz))
            return value.replace(tzinfo=tz)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_utc_to_tz(cls, utc_to_tz: IntLike(ge=-23, le=23)) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            try:
                cls.make_validator_must_be_utc(True)(value)
            except ValueError:
                return value
            tz = datetime.timezone(datetime.timedelta(hours=utc_to_tz))
            return value.astimezone(tz)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_tz_to_utc(cls, tz_to_utc: bool) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            if tz_to_utc:
                try:
                    cls.make_validator_must_be_aware(True)(value)
                except ValueError:
                    return value
                return value.astimezone(datetime.timezone.utc)
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_add_offset(
        cls,
        add_offset: datetime.timedelta | dateutil.relativedelta.relativedelta,
    ) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            return value + add_offset

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_gt(cls, gt: datetime.datetime) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            return validate_type(value, Annotated[datetime.datetime, Field(gt=gt)])
            # assert value > gt, f"Value must be greater than '{gt}'."
            # return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_ge(cls, ge: datetime.datetime) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            assert value >= ge, f"Value must be greater than or equal to '{ge}'."
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_lt(cls, lt: datetime.datetime) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            assert value < lt, f"Value must be less than '{lt}'."
            return value

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_le(cls, le: datetime.datetime) -> FuncDtDt:

        def validator(value: datetime.datetime) -> datetime.datetime:
            assert value <= le, f"Value must be less than or equal to '{le}'."
            return value

        return validator

    @BaseLikeInUserOrder._call_real_new
    def __new__(
        cls,
        *,
        title: str | None = None,
        description: str | None = None,
        examples: list[Any] | None = None,
        gt: datetime.datetime | None = None,
        ge: datetime.datetime | None = None,
        lt: datetime.datetime | None = None,
        le: datetime.datetime | None = None,
        dt_format: str | None = None,
        must_be_naive: bool | None = None,
        must_be_aware: bool | None = None,
        must_be_utc: bool | None = None,
        naive_to_utc: bool | None = None,
        naive_to_tz: int | None = None,
        utc_to_tz: int | None = None,
        tz_to_utc: bool | None = None,
        add_offset: datetime.timedelta | dateutil.relativedelta.relativedelta | None = None,
        config: Iterable[tuple[str, Any]] | None = None,
    ):
        pass

    @classmethod
    def _real_new(cls, config: MultiDict):

        before_validators_args = {
            "date_to_datetime": True,
            "dt64_to_datetime": True,
            "timestamp_to_datetime": True,
            "format": cls._popall_get_last(config, "format"),
            "str_to_datetime": True,
        }

        field_validators_args = {
            "title": cls._popall_get_last(config, "title"),
            "description": cls._popall_get_last(config, "description"),
            "examples": cls._popall_get_last(config, "examples"),
            # "gt": cls._popall_get_last(config, "gt"),
            # "ge": cls._popall_get_last(config, "ge"),
            # "lt": cls._popall_get_last(config, "lt"),
            # "le": cls._popall_get_last(config, "le"),
        }

        return cls._get_annotated(
            type=datetime.datetime,
            before_validators_args=before_validators_args,
            field_validators_args=field_validators_args,
            after_validators_args=config,
        )
