"""Контракты записи и чтения файла changelog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge.migration.domain.changelog import Changelog


class ChangelogUnreadableError(Exception):
    """Файл changelog не прочитать или он не в формате `forge generate`."""


@dataclass(frozen=True)
class ConstraintRef:
    """Ограничение в changelog: вид `foreign_key` или `unique`, таблица и имя."""

    kind: str
    table: str
    name: str


@dataclass(frozen=True)
class RowRef:
    """Строка в changelog данных: таблица, условие `where` на первичный ключ и литералы.

    `values` — пары «колонка → литерал SQL» из блока отката: прежние значения изменённых
    колонок или все значения удалённой строки; у вставленной строки пусто.
    """

    table: str
    where: str
    values: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ChangelogSummary:
    """Что changelog делает со схемой и строками: `id` changeset, добавляемые и удаляемые
    объекты, вставленные, изменённые и удалённые строки данных."""

    logical_file_path: str | None
    changeset_ids: tuple[str, ...]
    tables: tuple[str, ...]
    columns: tuple[tuple[str, str], ...]
    dropped_tables: tuple[str, ...] = ()
    dropped_columns: tuple[tuple[str, str], ...] = ()
    constraints: tuple[ConstraintRef, ...] = ()
    dropped_constraints: tuple[ConstraintRef, ...] = ()
    inserted_rows: tuple[RowRef, ...] = ()
    updated_rows: tuple[RowRef, ...] = ()
    deleted_rows: tuple[RowRef, ...] = ()


class ChangelogWriterInterface(Protocol):
    """Запись changelog в файл и удаление устаревшего файла."""

    def write(self, path: str, changelog: Changelog) -> None: ...

    def remove(self, path: str) -> None:
        """Удалить файл, если он есть."""
        ...


class ChangelogReaderInterface(Protocol):
    """Чтение changelog, построенного `forge generate`."""

    def read(self, path: str) -> ChangelogSummary:
        """Прочитать changelog; при ошибке — `ChangelogUnreadableError`."""
        ...

    def exists(self, path: str) -> bool:
        """Есть ли файл changelog."""
        ...
