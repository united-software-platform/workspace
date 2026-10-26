"""Внешний ключ таблицы модели данных."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.violation import ModelViolationError, Violation

if TYPE_CHECKING:
    from forge.modeling.domain.table import Table


@dataclass(frozen=True, eq=False)
class ForeignKey:
    """Внешний ключ: колонки своей таблицы, целевая таблица и колонки цели.

    Колонки FK и колонки цели образуют пары по позиции. Тождество — по целевой таблице
    и множеству пар: перестановка пар даёт тот же внешний ключ. Конструктор проверяет
    только сами списки; ссылки на колонки и цель проверяют `source_violations`
    и `target_violations`. Пути нарушений — относительно внешнего ключа.
    """

    columns: tuple[ColumnName, ...]
    target: TableName
    target_columns: tuple[ColumnName, ...]

    def __post_init__(self) -> None:
        violations = _list_violations(self.columns, "columns")
        violations += _list_violations(self.target_columns, "references.columns")
        if self.columns and self.target_columns and len(self.columns) != len(self.target_columns):
            violations.append(
                Violation(
                    "",
                    "foreign_key_column_count",
                    f"у внешнего ключа {len(self.columns)} колонок, "
                    f"у цели — {len(self.target_columns)}",
                )
            )
        if violations:
            raise ModelViolationError(violations)

    def pairs(self) -> frozenset[tuple[ColumnName, ColumnName]]:
        """Пары «колонка FK → колонка цели» без порядка."""
        return frozenset(zip(self.columns, self.target_columns, strict=True))

    def source_violations(self, source: Table) -> list[Violation]:
        """Нарушения ссылок на колонки своей таблицы."""
        return [
            Violation(
                f"columns[{position}]",
                "foreign_key_unknown_column",
                f"в таблице {source.name} нет колонки {column}",
            )
            for position, column in enumerate(self.columns)
            if not source.has_column(column)
        ]

    def target_violations(self, source: Table, target: Table) -> list[Violation]:
        """Нарушения ссылки на цель: колонки цели, ключ цели и типы пар.

        Цель — первичный ключ или набор уникальности целевой таблицы по составу. Тип колонки
        FK с параметрами совпадает с типом парной колонки цели; пара с неизвестной колонкой
        FK не сравнивается — о ней сообщает `source_violations`.
        """
        unknown = [
            Violation(
                f"references.columns[{position}]",
                "foreign_key_unknown_target_column",
                f"в таблице {target.name} нет колонки {column}",
            )
            for position, column in enumerate(self.target_columns)
            if not target.has_column(column)
        ]
        if unknown:
            return unknown
        violations: list[Violation] = []
        if not target.has_key(frozenset(self.target_columns)):
            listed = ", ".join(str(column) for column in self.target_columns)
            violations.append(
                Violation(
                    "references.columns",
                    "foreign_key_target_not_key",
                    f"колонки [{listed}] не первичный ключ и не набор unique таблицы {target.name}",
                )
            )
        for position, (column, target_column) in enumerate(
            zip(self.columns, self.target_columns, strict=True)
        ):
            if not source.has_column(column):
                continue
            own = source.column(column).type
            other = target.column(target_column).type
            if own != other:
                violations.append(
                    Violation(
                        f"columns[{position}]",
                        "foreign_key_type_mismatch",
                        f"тип {own} колонки {column} не совпадает с типом {other} "
                        f"колонки {target.name}.{target_column}",
                    )
                )
        return violations

    def __str__(self) -> str:
        """Запись для сообщений и сверки: `[customer_id] → customer[id]`."""
        own = ", ".join(str(column) for column in self.columns)
        other = ", ".join(str(column) for column in self.target_columns)
        return f"[{own}] → {self.target}[{other}]"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ForeignKey)
            and other.target == self.target
            and other.pairs() == self.pairs()
        )

    def __hash__(self) -> int:
        return hash((self.target, self.pairs()))


def duplicate_foreign_keys(keys: Iterable[tuple[int, ForeignKey]]) -> dict[int, Violation]:
    """Нарушения повтора внешних ключей таблицы по парам «позиция, внешний ключ».

    Ключ результата — позиция повторного внешнего ключа; путь — относительно таблицы.
    """
    first: dict[ForeignKey, int] = {}
    violations: dict[int, Violation] = {}
    for position, key in keys:
        if key in first:
            violations[position] = Violation(
                f"foreign_keys[{position}]",
                "foreign_key_duplicate",
                f"внешний ключ {key} уже объявлен в foreign_keys[{first[key]}]",
            )
        else:
            first[key] = position
    return violations


def _list_violations(columns: tuple[ColumnName, ...], path: str) -> list[Violation]:
    if not columns:
        return [Violation(path, "empty_foreign_key", "внешний ключ не содержит колонок")]
    seen: set[ColumnName] = set()
    violations: list[Violation] = []
    for position, column in enumerate(columns):
        if column in seen:
            violations.append(
                Violation(
                    f"{path}[{position}]",
                    "foreign_key_duplicate_column",
                    f"колонка {column} повторена во внешнем ключе",
                )
            )
        seen.add(column)
    return violations
