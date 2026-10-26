"""Контракты принятого состояния `db/` и результатов попыток."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AcceptanceError(Exception):
    """Принять файлы попытки в корень принятого состояния не удалось: нет файлов или записи."""


@dataclass(frozen=True)
class AcceptedFiles:
    """Файлы принятого состояния операции: главный файл, changelog операции и `master.yaml`.

    `model` — принятая модель операции модели; у операции seed — `None`. `seed` — принятый seed
    операции seed; у операции модели — только если закрытие изменило принятый seed.
    """

    model: str | None
    changelog: str
    master: str
    seed: str | None = None


class AcceptedStateInterface(Protocol):
    """Принятое состояние проекта."""

    def accept(self, stamp: str, attempt_directory: str) -> AcceptedFiles:
        """Принять модель и changelog попытки; повторное принятие ничего не меняет."""
        ...

    def files(self, stamp: str) -> AcceptedFiles:
        """Пути принятых файлов операции модели."""
        ...

    def accept_seed(self, stamp: str, attempt_directory: str) -> AcceptedFiles:
        """Принять seed и changelog данных попытки; модель не меняется, повтор ничего не меняет."""
        ...

    def seed_files(self, stamp: str) -> AcceptedFiles:
        """Пути принятых файлов операции seed."""
        ...


@dataclass(frozen=True)
class DiscrepancySummary:
    """Расхождение сверки попытки, как его записал `forge reconcile`."""

    kind: str
    table: str | None
    column: str | None
    changeset: str | None
    expected: str
    actual: str
    message: str


@dataclass(frozen=True)
class ReconcileSummary:
    """Итог сверки попытки из `reconcile.json`."""

    verdict: str
    discrepancies: tuple[DiscrepancySummary, ...]


@dataclass(frozen=True)
class RollbackSummary:
    """Итог отката попытки из `rollback.json`."""

    action: str
    rolled_back: int
    verified: bool
    fallback_reason: str | None


@dataclass(frozen=True)
class DestructiveChange:
    """Удаление итогового changelog: таблица и колонка; у удалённой таблицы колонка — `None`."""

    table: str
    column: str | None


@dataclass(frozen=True)
class DeletedRow:
    """Удаление changelog данных: таблица и первичный ключ строки — пары «колонка, значение»."""

    table: str
    key: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class TableRowCounts:
    """Число вставленных, изменённых и удалённых строк таблицы в changelog данных."""

    table: str
    inserted: int
    updated: int
    deleted: int


@dataclass(frozen=True)
class DataChanges:
    """Строки changelog данных: счётчики по таблицам в порядке появления и удалённые строки."""

    tables: tuple[TableRowCounts, ...]
    deleted: tuple[DeletedRow, ...]


class AttemptResultsReaderInterface(Protocol):
    """Результаты попытки: сверка и откат в её каталоге, удаления и строки её changelog."""

    def reconcile(self, attempt_directory: str) -> ReconcileSummary | None:
        """Итог сверки; нет файла — `None`."""
        ...

    def rollback(self, attempt_directory: str) -> RollbackSummary | None:
        """Итог отката; нет файла — `None`."""
        ...

    def destructive(self, changelog: str) -> tuple[DestructiveChange, ...]:
        """Удаления changelog; нет файла или он не читается — пустой перечень."""
        ...

    def data_changes(self, changelog: str) -> DataChanges:
        """Строки changelog данных; нет файла или он не читается — пустые перечни."""
        ...
