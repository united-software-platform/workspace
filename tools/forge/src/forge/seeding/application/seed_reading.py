"""Контракт чтения черновика seed из файла.

Контракт объявлен в слое приложения, а не в домене: его реализация обращается к файловой
системе (CLAR-006).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge.modeling.domain.violation import Violation
from forge.seeding.domain.draft import SeedDraft


@dataclass(frozen=True)
class SeedReading:
    """Результат чтения: черновик из таблиц без структурных нарушений и сами нарушения.

    Таблица со структурным нарушением в черновик не попадает; при нарушении корня файла
    черновик пуст.
    """

    draft: SeedDraft
    violations: tuple[Violation, ...]


class SeedUnreadableError(Exception):
    """Файл seed не прочитать: его нет, это каталог, нет прав или он не в UTF-8."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"файл seed {path} не прочитать: {reason}")
        self.path = path
        self.reason = reason


class SeedNotFoundError(SeedUnreadableError):
    """Файла seed нет."""

    def __init__(self, path: str) -> None:
        super().__init__(path, "файла нет")


class SeedDraftReaderInterface(Protocol):
    """Чтение файла seed и проверка его структуры."""

    def read(self, path: str) -> SeedReading:
        """Прочитать файл seed; нечитаемый файл — `SeedUnreadableError`."""
        ...
