"""Перечень допустимых значений колонки — ограничение `CHECK (<колонка> IN (…))`."""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.column_type import ColumnType, TypeKind
from forge.modeling.domain.violation import ModelViolationError, Violation

ListValue = str | int | bool | float | None
"""Значение перечня как записано в файле: вид проверяет колонка по своему типу."""

INTEGER_RANGES: dict[TypeKind, tuple[int, int]] = {
    TypeKind.INTEGER: (-(2**31), 2**31 - 1),
    TypeKind.BIGINT: (-(2**63), 2**63 - 1),
}
STRING_KINDS = frozenset({TypeKind.STRING, TypeKind.TEXT})
CHECK_KINDS = STRING_KINDS | frozenset(INTEGER_RANGES)


@dataclass(frozen=True, eq=False)
class ValueList:
    """Непустой перечень значений без повторов; тождество — по множеству значений.

    Порядок значений сохраняется для записи, но смысла не несёт: `[a, b]` и `[b, a]` —
    один перечень. Значения разного вида различаются: `1` и `"1"` — разные значения,
    логическое значение не совпадает с целым. Пути нарушений — относительно поля `check`.
    """

    values: tuple[ListValue, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ModelViolationError([Violation("", "check_empty", "перечень значений пуст")])
        first: dict[tuple[type, ListValue], int] = {}
        violations: list[Violation] = []
        for position, value in enumerate(self.values):
            key = _identity(value)
            if key in first:
                violations.append(
                    Violation(
                        f"[{position}]",
                        "check_duplicate_value",
                        f"значение {value!r} уже указано в check[{first[key]}]",
                    )
                )
            else:
                first[key] = position
        if violations:
            raise ModelViolationError(violations)

    def composition(self) -> frozenset[tuple[type, ListValue]]:
        """Множество значений без порядка: по нему перечни отождествляются."""
        return frozenset(_identity(value) for value in self.values)

    def sorted_values(self) -> tuple[ListValue, ...]:
        """Значения в каноническом порядке: строки и целые — по значению."""
        return tuple(sorted(self.values, key=lambda value: (type(value).__name__, value)))

    def kind_violations(self, column_type: ColumnType) -> list[Violation]:
        """Нарушения перечня у колонки такого типа: тип без перечня, вид и пределы значений."""
        if column_type.kind not in CHECK_KINDS:
            return [
                Violation(
                    "",
                    "check_unsupported_type",
                    f"у типа {column_type.kind} нет перечня значений: допустимы "
                    + ", ".join(sorted(kind.value for kind in CHECK_KINDS)),
                )
            ]
        violations: list[Violation] = []
        for position, value in enumerate(self.values):
            violation = _value_violation(column_type, value)
            if violation is not None:
                violations.append(violation.under(f"[{position}]"))
        return violations

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ValueList) and other.composition() == self.composition()

    def __hash__(self) -> int:
        return hash(self.composition())


def _identity(value: ListValue) -> tuple[type, ListValue]:
    return (type(value), value)


def _value_violation(column_type: ColumnType, value: ListValue) -> Violation | None:
    kind = column_type.kind
    if kind in STRING_KINDS:
        if not isinstance(value, str):
            return Violation("", "check_value_wrong_kind", f"у типа {kind} значение — строка")
        length = column_type.length
        if length is not None and len(value) > length:
            return Violation(
                "",
                "check_value_out_of_range",
                f"значение {value!r} длиннее {length} символов",
            )
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        return Violation("", "check_value_wrong_kind", f"у типа {kind} значение — целое число")
    low, high = INTEGER_RANGES[kind]
    if not low <= value <= high:
        return Violation(
            "",
            "check_value_out_of_range",
            f"значение должно быть от {low} до {high}, получено {value}",
        )
    return None
