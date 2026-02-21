"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = [
    "FloatLike",
    "IntLike",
    "ListLike",
    "PathLike",
    "StrLike",
    "set_type_annotations_and_validation",
    "set_validate_types_in_func_call",
    "validate_type",
    "validate_types_in_func_call",
]

from ._common import (
    set_type_annotations_and_validation,
    set_validate_types_in_func_call,
    validate_type,
    validate_types_in_func_call,
)
from ._floatlike import FloatLike
from ._intlike import IntLike
from ._listlike import ListLike
from ._pathlike import PathLike
from ._strlike import StrLike
