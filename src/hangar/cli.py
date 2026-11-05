"""The `hangar` command line."""

import argparse
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from hangar.pipelines.commands import run_command

DEFAULT_CONFIG = Path("configs/pipelines/v0.yaml")

COMMANDS = {
    "doctor": "check that this machine is ready to run Hangar",
    "fetch": "download the corpus documents and check their hashes",
    "parse": "turn each document into one canonical text",
    "chunk": "split the canonical texts into chunks",
    "embed": "turn the chunks into vectors",
    "index": "load the vectors into Qdrant",
    "search": "find the passages for a question, without the language model",
    "ask": "answer a question from the documents, with citations",
}

SEED_COMMANDS = {
    "run": "answer every seed question",
    "summarize": "summarize the scores of a seed run",
}


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for the `hangar` command.

    Returns:
        A parser with `--version` and one subcommand per pipeline stage.
        Every subcommand takes `--config`.
    """
    parser = argparse.ArgumentParser(
        prog="hangar",
        description="Hangar - cited answers from aircraft maintenance documents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"hangar {version('hangar')}",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, summary in COMMANDS.items():
        _add_command(commands, name, summary)

    seed = commands.add_parser("seed", help="run or summarize the seed questions")
    seed_commands = seed.add_subparsers(
        dest="seed_command", required=True, metavar="command"
    )
    for name, summary in SEED_COMMANDS.items():
        _add_command(seed_commands, name, summary)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the `hangar` command.

    Args:
        argv: The command-line arguments, without the program name.
            Defaults to the arguments the process was started with.

    Returns:
        The exit code: 0 on success, 1 when the command fails.
    """
    args = build_parser().parse_args(argv)
    command = args.command
    if command == "seed":
        command = f"seed {args.seed_command}"
    return run_command(command, args.config)


def _add_command(
    commands: "argparse._SubParsersAction[argparse.ArgumentParser]",
    name: str,
    summary: str,
) -> None:
    command = commands.add_parser(name, help=summary, description=summary)
    command.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="the pipeline file (default: %(default)s)",
    )
