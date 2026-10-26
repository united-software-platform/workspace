"""Таблица модели данных."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from forge.modeling.domain.column import Column
from forge.modeling.domain.foreign_key import ForeignKey, duplicate_foreign_keys
from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.primary_key import PrimaryKey
from forge.modeling.domain.unique_set import UniqueSet
from forge.modeling.domain.violation import ModelViolationError, Violation


@dataclass(frozen=True, eq=False)
class Table:
    """Таблица: идентичность по имени, колонки в порядке объявления, первичный ключ,
    наборы уникальности и внешние ключи.

    Инварианты: хотя бы одна колонка, имена колонок уникальны, ключ ссылается на колонки
    таблицы, у колонок ключа нет явного `nullable: true`; наборы уникальности ссылаются
    на колонки таблицы, не совпадают с ключом и между собой; внешние ключи ссылаются на колонки
    таблицы и не повторяются. Ссылку внешнего ключа на цель проверяет модель: цель — другая
    таблица. Все нарушения таблицы сообщаются сразу, с путями относительно таблицы.
    """

    name: TableName
    columns: tuple[Column, ...]
    primary_key: PrimaryKey
    unique: tuple[UniqueSet, ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()

    def __post_init__(self) -> None:
        violations = Table.violations_of(self.columns, self.primary_key, self.unique)
        if not violations:
            violations = self.foreign_key_violations(self.foreign_keys)
        if violations:
            raise ModelViolationError(violations)

    def foreign_key_violations(self, keys: Sequence[ForeignKey]) -> list[Violation]:
        """Нарушения внешних ключей против колонок этой таблицы: ссылки и повторы."""
        violations: list[Violation] = []
        valid: list[tuple[int, ForeignKey]] = []
        for position, key in enumerate(keys):
            found = key.source_violations(self)
            violations += [violation.under(f"foreign_keys[{position}]") for violation in found]
            if not found:
                valid.append((position, key))
        return violations + list(duplicate_foreign_keys(valid).values())

    @staticmethod
    def violations_of(
        columns: Sequence[Column],
        primary_key: PrimaryKey,
        unique: Sequence[UniqueSet | None] = (),
    ) -> list[Violation]:
        """Нарушения инвариантов таблицы из таких колонок, такого ключа и таких наборов.

        `None` в `unique` — набор, который не собран из-за собственных нарушений: позиции
        остальных наборов сохраняются, а сам он не проверяется.
        """
        violations: list[Violation] = []
        if not columns:
            violations.append(Violation("columns", "empty_columns", "таблица не содержит колонок"))
        positions: dict[ColumnName, int] = {}
        for position, column in enumerate(columns):
            if column.name in positions:
                violations.append(
                    Violation(
                        f"columns[{position}].name",
                        "duplicate_name",
                        f"колонка {column.name} уже объявлена в columns[{positions[column.name]}]",
                    )
                )
            else:
                positions[column.name] = position
        for position, name in enumerate(primary_key.columns):
            if name not in positions:
                violations.append(
                    Violation(
                        f"primary_key[{position}]",
                        "primary_key_unknown_column",
                        f"в таблице нет колонки {name}",
                    )
                )
        for position, column in enumerate(columns):
            if column.name in primary_key and column.nullable is True:
                violations.append(
                    Violation(
                        f"columns[{position}].nullable",
                        "primary_key_nullable",
                        f"колонка {column.name} входит в первичный ключ и не может допускать NULL",
                    )
                )
        return violations + _unique_violations(positions, primary_key, unique)

    def column(self, name: ColumnName) -> Column:
        """Колонка по имени; отсутствие колонки — ошибка вызывающей стороны."""
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"в таблице {self.name} нет колонки {name}")

    def has_column(self, name: ColumnName) -> bool:
        return any(column.name == name for column in self.columns)

    def has_key(self, columns: frozenset[ColumnName]) -> bool:
        """Совпадает ли состав колонок с первичным ключом или с одним из наборов уникальности."""
        if columns == frozenset(self.primary_key.columns):
            return True
        return any(columns == unique.composition() for unique in self.unique)

    def is_nullable(self, name: ColumnName) -> bool:
        """Итоговая допустимость NULL: колонки ключа NOT NULL, без `nullable` — NULL допустим."""
        column = self.column(name)
        return name not in self.primary_key and column.nullable is not False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Table) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)


def _unique_violations(
    positions: dict[ColumnName, int],
    primary_key: PrimaryKey,
    unique: Sequence[UniqueSet | None],
) -> list[Violation]:
    """Нарушения наборов уникальности: неизвестная колонка, совпадение с ключом, повтор.

    Совпадение и повтор проверяются только у набора, все колонки которого есть в таблице.
    """
    violations: list[Violation] = []
    key = frozenset(primary_key.columns)
    first: dict[frozenset[ColumnName], int] = {}
    for index, unique_set in enumerate(unique):
        if unique_set is None:
            continue
        unknown = [
            Violation(
                f"unique[{index}][{position}]",
                "unique_unknown_column",
                f"в таблице нет колонки {name}",
            )
            for position, name in enumerate(unique_set.columns)
            if name not in positions
        ]
        violations += unknown
        if unknown:
            continue
        composition = unique_set.composition()
        if composition == key:
            violations.append(
                Violation(
                    f"unique[{index}]",
                    "unique_equals_primary_key",
                    "набор уникальности совпадает с первичным ключом",
                )
            )
        elif composition in first:
            violations.append(
                Violation(
                    f"unique[{index}]",
                    "unique_duplicate",
                    f"набор уникальности уже объявлен в unique[{first[composition]}]",
                )
            )
        else:
            first[composition] = index
    return violations
