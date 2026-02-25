"""Type annotations to be used with Pydantic validation."""

from __future__ import annotations

__all__ = ["PathLike"]

import os
import random
import re
import string
from collections.abc import Callable, Iterable
from pathlib import Path
from re import Pattern
from typing import Any

from multidict import MultiDict

from ._baselike import BaseLikeInUserOrder
from ._common import (
     validate_types_in_func_call,
)


class PathLike(BaseLikeInUserOrder):
    """Create a PathLike type for validating file system paths with customizable constraints.

    Validators are applied in the user requested order.

    Parameters
    ----------
    title : str, optional
        Human-readable title. Useful for documentation and debugging.
    description : str, optional
        Human-readable description. Useful for documentation and debugging.
    examples : list[Any], optional
        Examples of valid values. Useful for documentation and debugging.
    exist : bool, optional
        Path must exist.
    exist_as_file : bool, optional
        Path must exist and be a file. Same as `pydantic.FilePath`.
    exist_as_dir : bool, optional
        Path must exist and be a directory. Same as `pydantic.DirectoryPath`.
    not_exist : bool, optional
        Path must not exist. Same as `pydantic.NewPath`.
    readable : bool, optional
        Path must be readable, i.e.: file/directory must exist and be readable.
    writable : bool, optional
        Path must be writable, i.e.: if file/directory exists, it must be writable.
        If it does not exist, the nearest existing parent directory must be writable.
    create_as_dir : bool, optional
        Create path as directory if it does not exist. Parents are created
        as needed.
    create_as_file : bool, optional
        Create path as empty file if it does not exist.
        Parents are created as needed.
    create_parents : bool, optional
        Create path up to parents directories. Same as `path.parent.mkdir(parents=True, exist_ok=True)`
    absolute : bool, optional
        Make the path absolute, normalizing it but not resolving symlinks.
        Same as `os.path.normpath(path.expanduser().absolute())`
    resolve : bool, optional
        Make the path absolute, normalizing it and resolving all symlinks on the way.
        Same as `path.expanduser().resolve()`
    endswith : str, optional
        Path must end with this string. Useful to check file extensions.
        Multiple suffixes can be provided separated by semicolons,
        e.g.: '.png;.gif;.jpeg'
    path_pattern : str, Pattern[str], optional
        Regular expression pattern that the full path must match.
    name_pattern : str, Pattern[str], optional
        Regular expression pattern that the path name (final component) must match.
    with_suffix : str, optional
        Path with the file suffix changed. If the path has no suffix, add given
        suffix. If the given suffix is an empty string, remove the suffix from
        the path. Same as `path.with_suffix(suffix)`.
    with_random_part : bool, optional
        Add a random string to the file name before the suffix. Useful to
        create temporary files.
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
    def make_validator_exist(cls, exist: bool) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if exist and not path.exists():
                msg = f"Path '{path}' does not exist."
                raise ValueError(msg)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_exist_as_file(
        cls,
        exist_as_file: bool,
    ) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if exist_as_file and not path.is_file():
                msg = f"Path '{path}' is not an existing file."
                raise ValueError(msg)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_exist_as_dir(
        cls,
        exist_as_dir: bool,
    ) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if exist_as_dir and not path.is_dir():
                msg = f"Path '{path}' is not an existing directory."
                raise ValueError(msg)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_not_exist(cls, not_exist: bool) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if not_exist and path.exists():
                msg = f"Path '{path}' exists."
                raise ValueError(msg)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_readable(cls, readable: bool) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if readable and not os.access(path, os.R_OK):
                msg = f"Path '{path}' is not readable."
                raise ValueError(msg)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_writable(cls, writable: bool) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:

            if not writable:
                return path

            if path.exists():
                # if file/dir exists, check if is writable
                if not os.access(path, os.W_OK):
                    msg = f"Path '{path}' is not writable."
                    raise ValueError(msg)

            else:
                # go up in the parent directories until we find a valid one
                for parent in path.parents:
                    if os.access(parent, os.W_OK):
                        break
                else:
                    msg = f"Path '{path}' is not writable."
                    raise ValueError(msg)

            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_create_as_dir(
        cls,
        create_as_dir: bool,
    ) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if create_as_dir and not path.is_dir():
                path.mkdir(parents=True)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_create_as_file(
        cls,
        create_as_file: bool,
    ) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if create_as_file and not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w") as fp:
                    pass
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_create_parents(
        cls,
        create_parents: bool,
    ) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if create_parents:
                path.parent.mkdir(parents=True, exist_ok=True)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_absolute(cls, absolute: bool) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if absolute:
                return Path(os.path.normpath(path.expanduser().absolute()))
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_resolve(cls, resolve: bool) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if resolve:
                return path.expanduser().resolve()
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_endswith(cls, endswith: str) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:

            # multiple suffixes separated by ';', e.g.: ".png;.gif;.jpeg"
            suffixes = endswith.split(";")
            for suffix in suffixes:
                if str(path).endswith(suffix.strip()):
                    return path

            suffixes_str = " or ".join([f"'{suffix}'" for suffix in suffixes])
            msg = f"Path '{path}' does not end with '{suffixes_str}'."
            raise ValueError(msg)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_path_pattern(
        cls,
        path_pattern: str | Pattern[str],
    ) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if not re.search(path_pattern, str(path)):
                err_msg = f"Path '{path}' does not match pattern '{path_pattern}'."
                raise ValueError(err_msg)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_name_pattern(
        cls,
        name_pattern: str | Pattern[str],
    ) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            if not re.search(name_pattern, path.name):
                err_msg = f"Path '{path.name}' does not match pattern '{name_pattern}'."
                raise ValueError(err_msg)
            return path

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_with_suffix(cls, suffix: str) -> Callable[[Path], Path]:

        def validator(path: Path) -> Path:
            return path.with_suffix(suffix)

        return validator

    @classmethod
    @validate_types_in_func_call
    def make_validator_with_random_part(
        cls,
        with_random_part: bool,
    ) -> Callable[[Path], Path]:

        sample_space = string.ascii_lowercase + string.ascii_uppercase + string.digits
        random_str = "".join(random.choices(sample_space, k=8))

        def validator(path: Path) -> Path:
            if with_random_part:
                return path.with_name(f"{path.stem}_{random_str}{path.suffix}")
            return path

        return validator

    @BaseLikeInUserOrder._call_real_new
    def __new__(
        cls,
        *,
        title: str | None = None,
        description: str | None = None,
        examples: list[Any] | None = None,
        exist: bool | None = None,
        exist_as_file: bool | None = None,
        exist_as_dir: bool | None = None,
        not_exist: bool | None = None,
        readable: bool | None = None,
        writable: bool | None = None,
        create_as_dir: bool | None = None,
        create_as_file: bool | None = None,
        create_parents: bool | None = None,
        absolute: bool | None = None,
        resolve: bool | None = None,
        endswith: str | None = None,
        path_pattern: str | Pattern[str] | None = None,
        name_pattern: str | Pattern[str] | None = None,
        with_suffix: str | None = None,
        with_random_part: bool | None = None,
        config: Iterable[tuple[str, Any]] | None = None,
    ):
        pass

    @classmethod
    def _real_new(cls, config: MultiDict):

        field_validators_args = {
            "title": cls._popall_get_last(config, "title"),
            "description": cls._popall_get_last(config, "description"),
            "examples": cls._popall_get_last(config, "examples"),
            "strict": False,  # allow coercion from str to Path
        }

        return cls._get_annotated(
            type=Path,
            field_validators_args=field_validators_args,
            after_validators_args=config,
        )
