"""Первичный ключ таблицы модели данных."""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.identifier import ColumnName
from forge.modeling.domain.violation import ModelViolationError, Violation


@dataclass(frozen=True)
class PrimaryKey:
    """Упорядоченный непустой список имён колонок без повторов; порядок значим.

    Пути нарушений — относительно поля `primary_key`: пустой для пустого ключа,
    `[N]` для повтора колонки на позиции N.
    """

    columns: tuple[ColumnName, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ModelViolationError(
                [Violation("", "empty_primary_key", "первичный ключ не содержит колонок")]
            )
        seen: set[ColumnName] = set()
        violations: list[Violation] = []
        for position, column in enumerate(self.columns):
            if column in seen:
                violations.append(
                    Violation(
                        f"[{position}]",
                        "primary_key_duplicate_column",
                        f"колонка {column} повторена в первичном ключе",
                    )
                )
            seen.add(column)
        if violations:
            raise ModelViolationError(violations)

    def __contains__(self, column: object) -> bool:
        return column in self.columns
