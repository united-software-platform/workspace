"""Колонка таблицы модели данных."""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.column_type import ColumnType, TypeKind
from forge.modeling.domain.generation import Generation
from forge.modeling.domain.identifier import ColumnName
from forge.modeling.domain.value_list import ValueList
from forge.modeling.domain.violation import ModelViolationError, Violation

_GENERATED_KINDS = frozenset({TypeKind.INTEGER, TypeKind.BIGINT})


@dataclass(frozen=True)
class Column:
    """Колонка: имя, тип, допустимость NULL, генерация значения и перечень значений.

    `nullable` хранит три состояния: `True`, `False` и `None` — не задано. Без третьего
    состояния таблица не отличила бы явное `nullable: true` у колонки ключа от умолчания.
    Итоговую допустимость NULL с учётом первичного ключа и генерации сообщает таблица.

    Инварианты: генерация — только у `integer` и `bigint` и без явного `nullable: true`;
    перечень — только у типов с перечнем, со значениями вида и пределов типа, и не вместе
    с генерацией. Пути нарушений — относительно колонки.
    """

    name: ColumnName
    type: ColumnType
    nullable: bool | None = None
    generated: Generation | None = None
    check: ValueList | None = None

    def __post_init__(self) -> None:
        violations = self.violations_of(self.type, self.nullable, self.generated, self.check)
        if violations:
            raise ModelViolationError(violations)

    @staticmethod
    def violations_of(
        column_type: ColumnType,
        nullable: bool | None,
        generated: Generation | None,
        check: ValueList | None,
    ) -> list[Violation]:
        """Нарушения сочетания типа, `nullable`, генерации и перечня у одной колонки."""
        violations: list[Violation] = []
        if generated is not None:
            if column_type.kind not in _GENERATED_KINDS:
                violations.append(
                    Violation(
                        "generated",
                        "generated_requires_integer",
                        f"генерация значения допустима у integer и bigint, тип колонки "
                        f"{column_type.kind}",
                    )
                )
            if nullable is True:
                violations.append(
                    Violation(
                        "nullable",
                        "generated_nullable",
                        "колонка с генерацией значения не может допускать NULL",
                    )
                )
        if check is not None:
            if generated is not None:
                violations.append(
                    Violation(
                        "check",
                        "check_with_generated",
                        "перечень значений не задаётся колонке с генерацией значения",
                    )
                )
            violations += [v.under("check") for v in check.kind_violations(column_type)]
        return violations
