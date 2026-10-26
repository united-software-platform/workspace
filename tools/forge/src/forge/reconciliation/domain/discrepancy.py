"""Расхождение — одно несоответствие, найденное сверкой."""

from __future__ import annotations

from dataclasses import dataclass

RowKey = tuple[tuple[str, int | bool | str | None], ...]
"""Первичный ключ строки: пары «колонка → значение» в нормализованной форме seed."""


@dataclass(frozen=True)
class Discrepancy:
    """Вид, объект (таблица, колонка либо `id` changeset), ожидаемое и фактическое значение.

    `key` — первичный ключ строки у расхождений строк сверки seed; у остальных — `None`.
    """

    kind: str
    table: str | None
    column: str | None
    changeset: str | None
    expected: str
    actual: str
    message: str
    key: RowKey | None = None
