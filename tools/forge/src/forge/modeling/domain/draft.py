"""Черновик модели данных: значения нужного вида, ещё не проверенные инвариантами.

Черновик — вход фабрики модели в терминах домена, без следов формата файла. Вид значений
(строка, целое число, логическое значение) уже гарантирован тем, кто черновик собрал.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.value_list import ListValue


@dataclass(frozen=True)
class ColumnDraft:
    """Колонка как объявлена: `None` у параметра, `nullable`, `generated` или `check` — поле
    не задано.

    Значения `check` — скаляры YAML как записаны: их вид проверяет колонка по своему типу.
    """

    name: str
    type: str
    nullable: bool | None = None
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    generated: str | None = None
    check: tuple[ListValue, ...] | None = None


@dataclass(frozen=True)
class ForeignKeyDraft:
    """Внешний ключ как объявлен: колонки своей таблицы, целевая таблица и колонки цели."""

    columns: tuple[str, ...]
    table: str
    target_columns: tuple[str, ...]


@dataclass(frozen=True)
class TableDraft:
    """Таблица как объявлена; `position` — её индекс в списке `tables` файла модели.

    Отсутствующие в файле `unique` и `foreign_keys` — пустые кортежи.
    """

    position: int
    name: str
    columns: tuple[ColumnDraft, ...]
    primary_key: tuple[str, ...]
    unique: tuple[tuple[str, ...], ...] = ()
    foreign_keys: tuple[ForeignKeyDraft, ...] = ()


@dataclass(frozen=True)
class DataModelDraft:
    """Таблицы, прошедшие проверку вида значений, в порядке файла модели.

    `excluded` — имена таблиц, объявленных в файле, но исключённых из черновика из-за
    структурных нарушений: внешний ключ на такую таблицу не проверяется, а не считается
    ссылкой на неизвестную таблицу.
    """

    tables: tuple[TableDraft, ...]
    excluded: tuple[str, ...] = ()
