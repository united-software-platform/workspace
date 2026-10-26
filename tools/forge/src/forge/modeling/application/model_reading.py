"""Контракт чтения черновика модели данных из файла.

Контракт объявлен в слое приложения, а не в домене: его реализация обращается к файловой
системе (CLAR-006).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge.modeling.domain.draft import DataModelDraft
from forge.modeling.domain.violation import Violation


@dataclass(frozen=True)
class DraftReading:
    """Результат чтения: черновик из таблиц без структурных нарушений и сами нарушения.

    Таблица со структурным нарушением в черновик не попадает; при нарушении корня файла
    черновик пуст.
    """

    draft: DataModelDraft
    violations: tuple[Violation, ...]


class ModelUnreadableError(Exception):
    """Файл модели не прочитать: его нет, это каталог, нет прав или он не в UTF-8."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"файл модели {path} не прочитать: {reason}")
        self.path = path
        self.reason = reason


class ModelNotFoundError(ModelUnreadableError):
    """Файла модели нет."""

    def __init__(self, path: str) -> None:
        super().__init__(path, "файла нет")


class ModelDraftReaderInterface(Protocol):
    """Чтение файла модели и проверка его структуры."""

    def read(self, path: str) -> DraftReading:
        """Прочитать файл модели; нечитаемый файл — `ModelUnreadableError`."""
        ...
