"""Изменения схемы, которые выражает changelog, и неподдерживаемые изменения модели."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from forge.modeling.domain.column import Column
from forge.modeling.domain.foreign_key import ForeignKey
from forge.modeling.domain.identifier import TableName
from forge.modeling.domain.table import Table
from forge.modeling.domain.unique_set import UniqueSet


@dataclass(frozen=True)
class CreateTable:
    """Новая таблица: колонки, NOT NULL и первичный ключ; её ограничения — отдельные изменения."""

    table: Table


@dataclass(frozen=True)
class AddColumn:
    """Новая колонка существующей таблицы с итоговой допустимостью NULL."""

    table: TableName
    column: Column
    nullable: bool


@dataclass(frozen=True)
class DropTable:
    """Удаляемая таблица; принятое определение с наборами уникальности нужно для отката.

    Внешние ключи таблицы и внешние ключи на неё удаляются отдельными изменениями.
    """

    table: Table


@dataclass(frozen=True)
class DropColumn:
    """Удаляемая колонка существующей таблицы; принятое определение нужно для отката."""

    table: TableName
    column: Column
    nullable: bool


@dataclass(frozen=True)
class AddUnique:
    """Новый набор уникальности таблицы."""

    table: TableName
    unique: UniqueSet


@dataclass(frozen=True)
class DropUnique:
    """Удаляемый набор уникальности существующей таблицы; набор нужен для отката."""

    table: TableName
    unique: UniqueSet


@dataclass(frozen=True)
class AddForeignKey:
    """Новый внешний ключ таблицы."""

    table: TableName
    key: ForeignKey


@dataclass(frozen=True)
class DropForeignKey:
    """Удаляемый внешний ключ принятой модели; ключ нужен для отката."""

    table: TableName
    key: ForeignKey


SchemaChange = (
    CreateTable
    | AddColumn
    | DropTable
    | DropColumn
    | AddUnique
    | DropUnique
    | AddForeignKey
    | DropForeignKey
)


@dataclass(frozen=True)
class UnsupportedChange:
    """Изменение модели, которое changelog не выражает: смена типа, NULL или первичного ключа."""

    code: str
    table: str
    column: str | None
    message: str


class UnsupportedChangeError(Exception):
    """Модель попытки требует неподдерживаемых изменений: перечислены все."""

    def __init__(self, changes: Iterable[UnsupportedChange]) -> None:
        self.changes: tuple[UnsupportedChange, ...] = tuple(changes)
        if not self.changes:
            raise ValueError("UnsupportedChangeError требует хотя бы одного изменения")
        super().__init__("; ".join(change.message for change in self.changes))
