"""Контракт чтения записи об операции из её беклога.

Беклог операции принадлежит контексту Операция; Миграции из него нужны только штамп,
вердикт и каталог попытки, режим и согласие на удаления.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from forge.migration.domain.stamp import OperationStamp


class OperationRecordUnavailableError(Exception):
    """Беклог операции не прочитать или в нём нет нужных значений."""


@dataclass(frozen=True)
class OperationRecord:
    """Штамп операции, вердикты попыток, каталог следа и согласие на удаления.

    `mode` — режим операции (`auto` или `interactive`), `None`, если беклог его не задаёт.
    `allow_drop` — согласие операции на удаления; беклог без поля означает `False`.
    """

    stamp: OperationStamp
    verdicts: Mapping[int, str | None]
    trail_directory: str
    attempt_directories: Mapping[int, str] = field(default_factory=dict)
    mode: str | None = None
    allow_drop: bool = False

    def verdict(self, attempt: int) -> str | None:
        """Вердикт попытки: `success`, `failure` либо `None`, пока сверки не было."""
        return self.verdicts.get(attempt)

    def attempt_directory(self, attempt: int) -> str:
        """Каталог артефактов попытки: из блока `trail` беклога, иначе по раскладке следа."""
        return self.attempt_directories.get(attempt, f"{self.trail_directory}/attempt-{attempt}")


class OperationRecordReaderInterface(Protocol):
    """Чтение записи об операции по пути её беклога."""

    def read(self, path: str) -> OperationRecord:
        """Прочитать беклог; при ошибке — `OperationRecordUnavailableError`."""
        ...
