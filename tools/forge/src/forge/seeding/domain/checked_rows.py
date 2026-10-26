"""Таблицы и строки seed после проверки значений: общий вход проверок ключей и ссылок."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from forge.modeling.domain.identifier import ColumnName
from forge.modeling.domain.table import Table
from forge.seeding.domain.seed import SeedRow
from forge.seeding.domain.seed_value import SeedValue


@dataclass(frozen=True, eq=False)
class CheckedRow:
    """Строка с проверенными значениями.

    `values` содержит только значения, прошедшие проверку, включая NULL пропущенных колонок,
    допускающих NULL. `complete` — у строки не нарушено ни одно значение: только такая строка
    участвует в проверках ключей.
    """

    position: int
    path: str
    values: dict[ColumnName, SeedValue]
    complete: bool

    def key(self, columns: Iterable[ColumnName]) -> tuple[SeedValue, ...] | None:
        """Значения колонок в заданном порядке; `None`, если хоть одно значение нарушено."""
        values = tuple(self.values.get(column) for column in columns)
        if any(value is None for value in values):
            return None
        return tuple(value for value in values if value is not None)

    def label(self, table: Table) -> str:
        """Строка для сообщений по первичному ключу: `order_status[code=draft]`; путь — если
        значение ключа нарушено."""
        key = self.key(table.primary_key.columns)
        if key is None:
            return self.path
        pairs = ", ".join(
            f"{column}={value}"
            for column, value in zip(table.primary_key.columns, key, strict=True)
        )
        return f"{table.name}[{pairs}]"

    def row(self, table: Table) -> SeedRow:
        """Строка домена; вызывается только для строки без нарушенных значений."""
        return SeedRow(tuple((column.name, self.values[column.name]) for column in table.columns))


@dataclass(frozen=True)
class CheckedTable:
    """Таблица модели, её индекс в списке `tables` файла seed и проверенные строки."""

    position: int
    table: Table
    rows: tuple[CheckedRow, ...]

    @property
    def name_path(self) -> str:
        return f"tables[{self.position}].name"
