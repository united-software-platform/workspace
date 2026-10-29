"""Фактическая схема целевой БД, полученная интроспекцией каталога PostgreSQL."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from forge.modeling.domain.column_type import ColumnType

# Признак генерации значения в БД: `identity` — BY DEFAULT, `identity_always` — ALWAYS
IDENTITY = "identity"
IDENTITY_ALWAYS = "identity_always"


@dataclass(frozen=True)
class ActualColumn:
    """Колонка в БД: тип модели, если тип PostgreSQL входит в формат, исходное имя типа,
    допустимость NULL и генерация значения — `identity`, `identity_always` или `None`."""

    name: str
    type: ColumnType | None
    database_type: str
    nullable: bool
    generated: str | None = None

    @property
    def type_text(self) -> str:
        """Тип в записи формата либо исходный тип PostgreSQL, если формат его не знает."""
        return str(self.type) if self.type is not None else self.database_type


@dataclass(frozen=True)
class ActualForeignKey:
    """Внешний ключ в БД без имени: колонки, целевая таблица и колонки цели в парном порядке."""

    columns: tuple[str, ...]
    target: str
    target_columns: tuple[str, ...]

    def pairs(self) -> frozenset[tuple[str, str]]:
        """Пары «колонка FK → колонка цели» без порядка."""
        return frozenset(zip(self.columns, self.target_columns, strict=True))

    def __str__(self) -> str:
        """Запись для расхождения: `[customer_id] → customer[id]`."""
        return f"[{', '.join(self.columns)}] → {self.target}[{', '.join(self.target_columns)}]"


CheckValue = str | int
"""Значение перечня, восстановленное из определения ограничения."""


@dataclass(frozen=True)
class ActualCheck:
    """Ограничение `CHECK` в БД без имени.

    Если определение — перечень значений одной колонки, `column` и `values` заданы; иначе
    оба `None`, и ограничение описывает только исходное определение `definition`.
    """

    definition: str
    column: str | None = None
    values: frozenset[CheckValue] | None = None

    def identity(self) -> tuple[str, frozenset[tuple[type, CheckValue]]] | None:
        """Колонка и множество значений с их видом; `None` у нераспознанного ограничения."""
        if self.column is None or self.values is None:
            return None
        return self.column, frozenset((type(value), value) for value in self.values)

    def __str__(self) -> str:
        """Запись для расхождения: перечень `[collector, manual]` либо исходное определение."""
        if self.values is None:
            return self.definition
        return list_text(sorted(self.values, key=lambda value: (type(value).__name__, value)))


def list_text(values: Iterable[object]) -> str:
    """Перечень значений в записи расхождения: `[collector, manual]`, `[1, 2]`."""
    return "[" + ", ".join(str(value) for value in values) + "]"


@dataclass(frozen=True)
class ActualTable:
    """Таблица в БД: колонки в порядке каталога, первичный ключ, если он есть,
    ограничения уникальности, внешние ключи и ограничения `CHECK` без имён."""

    name: str
    columns: tuple[ActualColumn, ...]
    primary_key: tuple[str, ...] | None
    unique: tuple[tuple[str, ...], ...] = ()
    foreign_keys: tuple[ActualForeignKey, ...] = ()
    checks: tuple[ActualCheck, ...] = ()

    def column(self, name: str) -> ActualColumn | None:
        return next((column for column in self.columns if column.name == name), None)


@dataclass(frozen=True)
class ActualSchema:
    """Таблицы схемы `public` без таблиц журнала Liquibase."""

    tables: tuple[ActualTable, ...]

    def table(self, name: str) -> ActualTable | None:
        return next((table for table in self.tables if table.name == name), None)
