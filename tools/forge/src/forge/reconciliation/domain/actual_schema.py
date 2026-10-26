"""Фактическая схема целевой БД, полученная интроспекцией каталога PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.column_type import ColumnType


@dataclass(frozen=True)
class ActualColumn:
    """Колонка в БД: тип модели, если тип PostgreSQL входит в формат, и исходное имя типа."""

    name: str
    type: ColumnType | None
    database_type: str
    nullable: bool

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


@dataclass(frozen=True)
class ActualTable:
    """Таблица в БД: колонки в порядке каталога, первичный ключ, если он есть,
    ограничения уникальности и внешние ключи без имён."""

    name: str
    columns: tuple[ActualColumn, ...]
    primary_key: tuple[str, ...] | None
    unique: tuple[tuple[str, ...], ...] = ()
    foreign_keys: tuple[ActualForeignKey, ...] = ()

    def column(self, name: str) -> ActualColumn | None:
        return next((column for column in self.columns if column.name == name), None)


@dataclass(frozen=True)
class ActualSchema:
    """Таблицы схемы `public` без таблиц журнала Liquibase."""

    tables: tuple[ActualTable, ...]

    def table(self, name: str) -> ActualTable | None:
        return next((table for table in self.tables if table.name == name), None)
