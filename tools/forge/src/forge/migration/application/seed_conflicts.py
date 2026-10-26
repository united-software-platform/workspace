"""Контракт проверки принятого seed по модели попытки (CLAR-006: реализация читает файл)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge.modeling.domain.data_model import DataModel


class AcceptedSeedError(Exception):
    """Принятый seed существует, но его не прочитать."""


@dataclass(frozen=True)
class SeedConflict:
    """Конфликт модели попытки с принятым seed.

    `kind` — `seeded_table_dropped`, `not_null_column_added`, `foreign_key_violated_by_seed`
    или `unique_violated_by_seed`; `column` — у новой колонки NOT NULL, иначе `None`;
    `path` — место в принятом seed, `message` — нарушение, по которому найден конфликт.
    """

    kind: str
    table: str
    column: str | None
    path: str
    message: str


class SeedConflictCheckerInterface(Protocol):
    """Проверить принятый seed по модели попытки."""

    def check(
        self, seed_path: str, model: DataModel, dropped_columns: tuple[tuple[str, str], ...]
    ) -> tuple[SeedConflict, ...]:
        """Конфликты seed по модели после снятия ключей удалённых колонок `(таблица, колонка)`.

        Нет файла seed — конфликтов нет; нечитаемый файл — `AcceptedSeedError`.
        """
        ...
