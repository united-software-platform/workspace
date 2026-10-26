"""Контракт чтения операции (CQRS-003) и её модель чтения."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class OperationUnavailableError(Exception):
    """Беклог операции не прочитать либо его фронтматтер не описывает операцию."""


class SeveralOpenOperationsError(Exception):
    """В следах всех видов вместе больше одной открытой операции: навык держит открытой одну."""

    def __init__(self, paths: tuple[str, ...]) -> None:
        super().__init__(f"открытых операций больше одной: {', '.join(paths)}")
        self.paths = paths


@dataclass(frozen=True)
class OperationRecord:
    """Значения фронтматтера беклога операции.

    Беклог без `allow_drop` даёт `False`, беклог без `kind` — операцию модели `model`,
    беклог без `seed_adjusted` — `False`.
    """

    path: str
    stamp: str
    intent: str
    mode: str
    status: str
    stop_reason: str | None
    verdicts: Mapping[int, str | None]
    backlogs: Mapping[int, str | None]
    directories: Mapping[int, str]
    allow_drop: bool = False
    kind: str = "model"
    seed_adjusted: bool = False


class OperationReadRepositoryInterface(Protocol):
    """Чтение операций из следов всех видов."""

    def get(self, path: str) -> OperationRecord:
        """Операция по пути её беклога; ошибка — `OperationUnavailableError`."""
        ...

    def open_operations(self) -> tuple[str, ...]:
        """Пути беклогов операций со статусом `running` или `stopped` в следах всех видов."""
        ...
