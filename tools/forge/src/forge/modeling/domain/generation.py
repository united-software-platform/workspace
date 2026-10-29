"""Способ генерации значения колонки базой данных."""

from __future__ import annotations

from enum import StrEnum

from forge.modeling.domain.violation import ModelViolationError, Violation


class Generation(StrEnum):
    """Способ генерации из перечня формата.

    `identity` — значение выдаёт БД, а явное значение при вставке допускается: режим
    `BY DEFAULT`, потому что seed вставляет справочники с явными ключами.
    """

    IDENTITY = "identity"


def parse_generation(name: str) -> Generation:
    """Способ генерации по значению поля `generated`; неизвестное — `unknown_generation`."""
    try:
        return Generation(name)
    except ValueError:
        allowed = ", ".join(generation.value for generation in Generation)
        raise ModelViolationError(
            [
                Violation(
                    "generated",
                    "unknown_generation",
                    f"способ генерации {name!r} не входит в перечень: {allowed}",
                )
            ]
        ) from None
