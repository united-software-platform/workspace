"""Контракты прямого доступа к целевой БД: журнал Liquibase, наличие объектов и строк,
пересоздание."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge.migration.application.changelog_storage import RowRef
from forge.shared.domain.target_database import TargetDatabase


@dataclass(frozen=True)
class JournalEntry:
    """Запись `DATABASECHANGELOG`: changeset, автор, файл и порядок исполнения."""

    id: str
    author: str
    filename: str
    order: int


class JournalReaderInterface(Protocol):
    """Чтение журнала Liquibase в порядке исполнения; нет таблицы журнала — пустой журнал."""

    def entries(self, database: TargetDatabase) -> tuple[JournalEntry, ...]: ...


class SchemaProbeInterface(Protocol):
    """Есть ли таблица, колонка или ограничение в схеме `public`."""

    def table_exists(self, database: TargetDatabase, table: str) -> bool: ...

    def column_exists(self, database: TargetDatabase, table: str, column: str) -> bool: ...

    def constraint_exists(self, database: TargetDatabase, table: str, name: str, kind: str) -> bool:
        """Есть ли у таблицы ограничение с таким именем вида `foreign_key`, `unique` или `check`."""
        ...


class RowProbeInterface(Protocol):
    """Число строк таблицы схемы `public` по условию из changelog данных."""

    def count_rows(self, database: TargetDatabase, row: RowRef) -> int:
        """`count(*)` строк по условию `where` строки, где каждая колонка из `values`
        `IS NOT DISTINCT FROM` своего литерала; нет таблицы — `0`."""
        ...


class DatabaseRecreatorInterface(Protocol):
    """Удалить целевую БД и создать её заново пустой."""

    def recreate(self, database: TargetDatabase) -> None: ...
