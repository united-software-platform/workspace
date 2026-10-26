"""Входной контракт сценария отката попытки."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RollbackAttemptInput:
    """Беклог операции, номер попытки и признак отката при отказе от операции.

    С `discard` откатывается и попытка с вердиктом `success`: его ставит только `forge abandon`,
    у `forge rollback` такого ключа нет.
    """

    operation_path: str
    attempt: int
    discard: bool = False
