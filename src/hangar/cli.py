"""The `hangar` command line."""

import argparse
from collections.abc import Sequence
from importlib.metadata import version


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for the `hangar` command.

    Returns:
        A parser that understands `--version`. Later issues add one
        subcommand per pipeline stage.
    """
    parser = argparse.ArgumentParser(prog="hangar")
    parser.add_argument(
        "--version",
        action="version",
        version=f"hangar {version('hangar')}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """
    Run the `hangar` command.

    Args:
        argv: The command-line arguments, without the program name.
            Defaults to the arguments the process was started with.
    """
    build_parser().parse_args(argv)
