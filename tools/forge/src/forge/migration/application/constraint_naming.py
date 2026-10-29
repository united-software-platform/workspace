"""Контракт имён ограничений, которые changelog создаёт и удаляет.

Имя — знание о Liquibase и СУБД (предел длины идентификатора), поэтому реализация живёт
в инфраструктуре, а сценарии получают её через контракт.
"""

from __future__ import annotations

from typing import Protocol

from forge.modeling.domain.foreign_key import ForeignKey
from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.unique_set import UniqueSet
from forge.modeling.domain.value_list import ValueList


class ConstraintNamingInterface(Protocol):
    """Имена ограничений, вычисляемые из содержимого: одно содержимое — одно имя."""

    def unique(self, table: TableName, unique: UniqueSet) -> str:
        """Имя ограничения уникальности набора таблицы."""
        ...

    def foreign_key(self, table: TableName, key: ForeignKey) -> str:
        """Имя ограничения внешнего ключа таблицы."""
        ...

    def check(self, table: TableName, column: ColumnName, values: ValueList) -> str:
        """Имя ограничения перечня значений колонки таблицы."""
        ...
