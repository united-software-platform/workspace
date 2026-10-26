"""Общий контракт вывода команд `forge`.

Каждая команда печатает в стандартный вывод ровно один JSON-объект, диагностика уходит только
в стандартный поток ошибок. Коды возврата едины для всех команд.
"""

from __future__ import annotations

import json
import sys
from enum import IntEnum
from typing import Any, TextIO


class ExitCode(IntEnum):
    """Коды возврата команд `forge`."""

    SUCCESS = 0
    """Команда выполнена, операция успешна."""

    FAILURE = 1
    """Команда выполнена, но операция неуспешна: модель некорректна, есть расхождения и т.п."""

    ENVIRONMENT_ERROR = 2
    """Ошибка вызова или окружения: неверные аргументы, недоступная БД, раннер не отвечает."""


def emit(payload: dict[str, Any], stream: TextIO | None = None) -> None:
    """Напечатать единственный JSON-объект результата команды."""
    target = stream if stream is not None else sys.stdout
    target.write(json.dumps(payload, ensure_ascii=False))
    target.write("\n")


def error_payload(kind: str, message: str, **details: Any) -> dict[str, Any]:
    """Собрать JSON-объект ошибки: вид ошибки, сообщение и необязательные подробности."""
    error: dict[str, Any] = {"kind": kind, "message": message}
    error.update(details)
    return {"error": error}


def environment_error(kind: str, message: str, **details: Any) -> ExitCode:
    """Сообщить об ошибке вызова или окружения: диагностика в stderr, JSON в stdout, код `2`."""
    sys.stderr.write(f"forge: {message}\n")
    emit(error_payload(kind, message, **details))
    return ExitCode.ENVIRONMENT_ERROR
