"""Набор уникальности таблицы модели данных."""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.identifier import ColumnName
from forge.modeling.domain.violation import ModelViolationError, Violation


@dataclass(frozen=True, eq=False)
class UniqueSet:
    """Непустой список имён колонок без повторов; тождество — по составу колонок.

    Порядок колонок сохраняется для changelog, но смысла не несёт: `[a, b]` и `[b, a]` —
    один набор. Пути нарушений — относительно набора: пустой для пустого набора,
    `[N]` для повтора колонки на позиции N.
    """

    columns: tuple[ColumnName, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ModelViolationError(
                [Violation("", "empty_unique", "набор уникальности не содержит колонок")]
            )
        seen: set[ColumnName] = set()
        violations: list[Violation] = []
        for position, column in enumerate(self.columns):
            if column in seen:
                violations.append(
                    Violation(
                        f"[{position}]",
                        "unique_duplicate_column",
                        f"колонка {column} повторена в наборе уникальности",
                    )
                )
            seen.add(column)
        if violations:
            raise ModelViolationError(violations)

    def composition(self) -> frozenset[ColumnName]:
        """Состав набора без порядка."""
        return frozenset(self.columns)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, UniqueSet) and other.composition() == self.composition()

    def __hash__(self) -> int:
        return hash(self.composition())
