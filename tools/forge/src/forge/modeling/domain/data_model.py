"""Модель данных — корень агрегата контекста Моделирование."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from forge.modeling.domain.identifier import TableName
from forge.modeling.domain.table import Table
from forge.modeling.domain.violation import ModelViolationError, Violation

FORMAT_VERSION = 1


@dataclass(frozen=True)
class DataModel:
    """Полное целевое состояние схемы `public`: таблицы в порядке объявления.

    Инварианты агрегата — уникальность имён таблиц и ссылки внешних ключей на таблицы модели
    и их ключи; инварианты каждой таблицы обеспечивает сама таблица. Модель без таблиц
    корректна: так выглядит принятая модель до первой операции.
    """

    tables: tuple[Table, ...]

    def __post_init__(self) -> None:
        violations = list(
            DataModel.duplicate_names(enumerate(table.name for table in self.tables)).values()
        )
        if not violations:
            violations = self._reference_violations()
        if violations:
            raise ModelViolationError(violations)

    def _reference_violations(self) -> list[Violation]:
        violations: list[Violation] = []
        for position, table in enumerate(self.tables):
            for index, key in enumerate(table.foreign_keys):
                prefix = f"tables[{position}].foreign_keys[{index}]"
                if not self.has_table(key.target):
                    violations.append(unknown_target(key.target).under(prefix))
                    continue
                found = key.target_violations(table, self.table(key.target))
                violations += [violation.under(prefix) for violation in found]
        return violations

    @staticmethod
    def duplicate_names(names: Iterable[tuple[int, TableName]]) -> dict[int, Violation]:
        """Нарушения уникальности имён таблиц по парам «позиция в модели, имя».

        Ключ результата — позиция повторной таблицы, по одному нарушению на позицию.
        """
        first: dict[TableName, int] = {}
        violations: dict[int, Violation] = {}
        for position, name in names:
            if name in first:
                violations[position] = Violation(
                    f"tables[{position}].name",
                    "duplicate_name",
                    f"таблица {name} уже объявлена в tables[{first[name]}]",
                )
            else:
                first[name] = position
        return violations

    def table(self, name: TableName) -> Table:
        """Таблица по имени; отсутствие таблицы — ошибка вызывающей стороны."""
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(f"в модели нет таблицы {name}")

    def has_table(self, name: TableName) -> bool:
        return any(table.name == name for table in self.tables)


def unknown_target(name: object) -> Violation:
    """Нарушение ссылки внешнего ключа на таблицу, которой нет в модели; путь — от ключа."""
    return Violation(
        "references.table", "foreign_key_unknown_table", f"в модели нет таблицы {name}"
    )
