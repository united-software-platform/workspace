"""Выходной контракт сценария построения changelog данных."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataChangeSetView:
    """Changeset данных в ответе: `id`, вид `insert_rows`, `update_rows` или `delete_rows`,
    таблица и число строк."""

    id: str
    kind: str
    table: str
    rows: int


@dataclass(frozen=True)
class DeletedRowView:
    """Удаляемая строка: таблица и значения первичного ключа в порядке ключа."""

    table: str
    key: tuple[tuple[str, int | bool | str | None], ...]


@dataclass(frozen=True)
class SeedViolationView:
    """Нарушение seed попытки, как у `forge validate-seed`."""

    path: str
    code: str
    message: str


@dataclass(frozen=True)
class UnsupportedRowChangeView:
    """Неисполнимое изменение строк: набор `unique`, строки и сообщение."""

    code: str
    table: str
    columns: tuple[str, ...]
    rows: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class GenerateSeedChangelogOutput:
    """Итог: путь changelog при успехе, иначе нарушения seed или неисполнимые изменения."""

    changelog_path: str | None
    logical_file_path: str
    changesets: tuple[DataChangeSetView, ...]
    deleted_rows: tuple[DeletedRowView, ...]
    violations: tuple[SeedViolationView, ...]
    unsupported: tuple[UnsupportedRowChangeView, ...]
    generated: bool
