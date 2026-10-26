"""Контракт чтения фактических строк таблиц seed из целевой БД.

Контракт объявлен в слое приложения: его реализация обращается к БД (CLAR-006).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from forge.modeling.domain.identifier import TableName
from forge.modeling.domain.table import Table
from forge.seeding.domain.seed import SeedRow
from forge.shared.domain.target_database import TargetDatabase


class TableRowsReaderInterface(Protocol):
    """Строки заданных таблиц в нормализованной форме seed по возрастанию первичного ключа."""

    def rows(
        self, database: TargetDatabase, tables: Sequence[Table]
    ) -> dict[TableName, tuple[SeedRow, ...]]:
        """Прочитать только заданные таблицы; ошибка запроса или значение, не приводимое к типу
        колонки модели, — `DatabaseUnavailableError`."""
        ...
