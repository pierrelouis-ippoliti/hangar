"""Errors that Hangar raises on purpose, each saying what is wrong and where."""

from collections.abc import Sequence
from dataclasses import dataclass

import pydantic
from pydantic_core import ErrorDetails


class HangarError(Exception):
    """Base class for the errors Hangar raises on purpose."""


@dataclass(frozen=True)
class FieldProblem:
    """
    One problem found in a configuration or manifest file.

    Attributes:
        field: The path to the field, such as ``chunking.size`` or
            ``parsing.car.subparts[1]``, or None when the problem is
            with the file as a whole.
        message: What is wrong, in plain words.
    """

    field: str | None
    message: str


class ConfigError(HangarError):
    """
    A configuration or manifest file that can't be used.

    The message has one line per problem, each starting with the file
    and the field, such as ``configs/pipelines/v0.yaml: chunking.size:
    Input should be greater than 0``.

    Attributes:
        source: The file the problems were found in.
        problems: Every problem found, in the order they were found.
    """

    def __init__(self, source: str, problems: Sequence[FieldProblem]) -> None:
        """
        Create the error.

        Args:
            source: The file the problems were found in.
            problems: Every problem found. At least one.
        """
        self.source = source
        self.problems = tuple(problems)
        super().__init__("\n".join(_describe(source, p) for p in self.problems))


def field_problems(error: pydantic.ValidationError) -> list[FieldProblem]:
    """
    Turn a pydantic validation error into problems that name their field.

    Args:
        error: The error raised while validating a file's content.

    Returns:
        One problem per failed check, with the field written as a dotted
        path and list positions in brackets.
    """
    return [
        FieldProblem(field=_field_path(detail["loc"]), message=_message(detail))
        for detail in error.errors()
    ]


def _describe(source: str, problem: FieldProblem) -> str:
    if problem.field is None:
        return f"{source}: {problem.message}"

    return f"{source}: {problem.field}: {problem.message}"


def _field_path(location: tuple[int | str, ...]) -> str | None:
    path = ""

    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else part

    return path or None


def _message(detail: ErrorDetails) -> str:
    # A check written as a plain function raises ValueError, which
    # pydantic reports as "Value error, <message>". Keep only the message.
    if detail["type"] == "value_error" and "ctx" in detail:
        return str(detail["ctx"]["error"])

    return detail["msg"]
