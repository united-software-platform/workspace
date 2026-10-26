"""Изменения строк seed, которые выражает changelog данных, и неисполнимые изменения."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from forge.modeling.domain.identifier import ColumnName
from forge.modeling.domain.table import Table
from forge.seeding.domain.seed import SeedRow
from forge.seeding.domain.seed_value import SeedValue


class RowChangeKind(StrEnum):
    """Вид изменения строки; changeset данных содержит изменения одного вида."""

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True)
class RowInsert:
    """Строка seed попытки, которой нет в принятом seed."""

    table: Table
    row: SeedRow

    @property
    def kind(self) -> RowChangeKind:
        return RowChangeKind.INSERT

    def key(self) -> tuple[tuple[ColumnName, SeedValue], ...]:
        return primary_key(self.table, self.row)


@dataclass(frozen=True)
class RowUpdate:
    """Строка с тем же первичным ключом и другими значениями: принятая и новая."""

    table: Table
    before: SeedRow
    after: SeedRow

    @property
    def kind(self) -> RowChangeKind:
        return RowChangeKind.UPDATE

    def key(self) -> tuple[tuple[ColumnName, SeedValue], ...]:
        return primary_key(self.table, self.after)

    def changed(self) -> tuple[ColumnName, ...]:
        """Колонки с отличающимися значениями в порядке модели."""
        return tuple(
            column
            for (column, old), (_, new) in zip(self.before.values, self.after.values, strict=True)
            if old != new
        )


@dataclass(frozen=True)
class RowDelete:
    """Строка принятого seed, которой нет в seed попытки; значения нужны для отката."""

    table: Table
    row: SeedRow

    @property
    def kind(self) -> RowChangeKind:
        return RowChangeKind.DELETE

    def key(self) -> tuple[tuple[ColumnName, SeedValue], ...]:
        return primary_key(self.table, self.row)


RowChange = RowInsert | RowUpdate | RowDelete


@dataclass(frozen=True)
class RowGroup:
    """Соседние в порядке исполнения изменения строк одной таблицы и одного вида."""

    kind: RowChangeKind
    table: Table
    changes: tuple[RowChange, ...]


def primary_key(table: Table, row: SeedRow) -> tuple[tuple[ColumnName, SeedValue], ...]:
    """Пары «колонка → значение» первичного ключа строки в порядке ключа."""
    return tuple((column, row.value(column)) for column in table.primary_key.columns)


def row_label(table: Table, row: SeedRow) -> str:
    """Строка для сообщений по первичному ключу: `order_status[code=draft]`."""
    pairs = ", ".join(f"{column}={value}" for column, value in primary_key(table, row))
    return f"{table.name}[{pairs}]"


@dataclass(frozen=True)
class UnsupportedRowChange:
    """Изменения строк, которые не исполнить ни в каком порядке без нарушения набора `unique`.

    `rows` — строка, занимающая значение набора, и строка, которая его освобождает.
    """

    code: str
    table: str
    columns: tuple[str, ...]
    rows: tuple[str, ...]
    message: str


class UnsupportedRowChangeError(Exception):
    """Seed попытки требует неисполнимых изменений строк: перечислены все."""

    def __init__(self, changes: Iterable[UnsupportedRowChange]) -> None:
        self.changes: tuple[UnsupportedRowChange, ...] = tuple(changes)
        if not self.changes:
            raise ValueError("UnsupportedRowChangeError требует хотя бы одного изменения")
        super().__init__("; ".join(change.message for change in self.changes))
