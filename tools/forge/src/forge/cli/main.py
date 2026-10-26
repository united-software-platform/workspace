"""Точка входа CLI `forge`.

Разбирает аргументы и передаёт управление команде. Ошибка разбора не печатает справку
`argparse` в стандартный вывод: она становится JSON-объектом ошибки с кодом `2`, чтобы
стандартный вывод любой команды оставался ровно одним JSON-объектом.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import NoReturn

from forge.cli.commands import COMMANDS
from forge.cli.contract import ExitCode, emit, error_payload


class UsageError(Exception):
    """Ошибка разбора аргументов командной строки."""

    def __init__(self, message: str, usage: str) -> None:
        super().__init__(message)
        self.usage = usage


class _Parser(argparse.ArgumentParser):
    """Парсер, который сообщает об ошибке исключением, а не печатью и выходом."""

    def error(self, message: str) -> NoReturn:
        raise UsageError(message, self.format_usage().strip())


def build_parser() -> argparse.ArgumentParser:
    """Собрать парсер: каждая команда регистрирует свою подкоманду и обработчик."""
    parser = _Parser(prog="forge", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    for command in COMMANDS:
        command.register(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Выполнить команду и вернуть код возврата."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except UsageError as error:
        sys.stderr.write(f"forge: {error}\n")
        emit(error_payload("usage", str(error), usage=error.usage))
        return ExitCode.ENVIRONMENT_ERROR

    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
