"""Колонка таблицы модели данных."""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.column_type import ColumnType
from forge.modeling.domain.identifier import ColumnName


@dataclass(frozen=True)
class Column:
    """Колонка: имя, тип и допустимость NULL в том виде, как она объявлена.

    `nullable` хранит три состояния: `True`, `False` и `None` — не задано. Без третьего
    состояния таблица не отличила бы явное `nullable: true` у колонки ключа от умолчания.
    Итоговую допустимость NULL с учётом первичного ключа сообщает таблица.
    """

    name: ColumnName
    type: ColumnType
    nullable: bool | None = None
