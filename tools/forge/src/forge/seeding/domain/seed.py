"""Seed — полное целевое состояние строк справочных таблиц, корень агрегата контекста Наполнение."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.table import Table
from forge.modeling.domain.violation import Violation
from forge.seeding.domain.seed_value import SeedValue


@dataclass(frozen=True)
class SeedRow:
    """Строка таблицы seed: значение каждой колонки таблицы в порядке модели.

    Колонка, не записанная в файле, хранится как NULL. Идентичность строки — значения
    первичного ключа таблицы.
    """

    values: tuple[tuple[ColumnName, SeedValue], ...]

    def value(self, name: ColumnName) -> SeedValue:
        for column, value in self.values:
            if column == name:
                return value
        raise KeyError(f"в строке нет колонки {name}")

    def key(self, columns: Iterable[ColumnName]) -> tuple[SeedValue, ...]:
        """Значения колонок в заданном порядке: ключ строки по PK, набору или FK."""
        return tuple(self.value(column) for column in columns)


@dataclass(frozen=True)
class SeedTable:
    """Таблица модели и все её строки: таблица из seed принадлежит ему целиком."""

    table: Table
    rows: tuple[SeedRow, ...]

    @property
    def name(self) -> TableName:
        return self.table.name


@dataclass(frozen=True)
class Seed:
    """Таблицы seed в порядке файла.

    Seed создаётся фабрикой `SeedFactory`: она проверяет значения, ключи и ссылки строк
    по модели данных. Таблицы модели вне seed им не затрагиваются.
    """

    tables: tuple[SeedTable, ...]

    def table(self, name: TableName) -> SeedTable:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(f"в seed нет таблицы {name}")

    def has_table(self, name: TableName) -> bool:
        return any(table.name == name for table in self.tables)


class SeedViolationError(Exception):
    """Seed нарушает формат или не согласован с моделью: объект не создан, нарушения перечислены."""

    def __init__(self, violations: Iterable[Violation]) -> None:
        self.violations: tuple[Violation, ...] = tuple(violations)
        if not self.violations:
            raise ValueError("SeedViolationError требует хотя бы одного нарушения")
        super().__init__("; ".join(f"{v.path}: {v.message}" for v in self.violations))
