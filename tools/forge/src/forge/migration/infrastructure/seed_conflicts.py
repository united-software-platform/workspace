"""Проверка принятого seed по модели попытки: Anti-Corruption Layer к контексту Наполнение.

Проверка — `forge validate-seed` принятого seed по модели попытки: тот же разборщик и та же
фабрика seed. Перед проверкой из строк снимаются ключи колонок, которые модель попытки удаляет:
Liquibase снимает колонку вместе с данными, а закрытие операции модели правит принятый seed.
Принятый seed проходил проверку по принятой модели, поэтому каждое оставшееся нарушение вызвано
изменением модели и переводится в вид конфликта по коду нарушения.
"""

from __future__ import annotations

import re

from forge.migration.application.seed_conflicts import AcceptedSeedError, SeedConflict
from forge.modeling.domain.data_model import DataModel
from forge.modeling.domain.violation import Violation
from forge.seeding.application.seed_reading import (
    SeedDraftReaderInterface,
    SeedNotFoundError,
    SeedUnreadableError,
)
from forge.seeding.domain.draft import RowDraft, SeedDraft, SeedTableDraft
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.domain.seed import SeedViolationError

KINDS = {
    "unknown_table": "seeded_table_dropped",
    "null_value": "not_null_column_added",
    "unresolved_reference": "foreign_key_violated_by_seed",
    "unseeded_reference_table": "foreign_key_violated_by_seed",
    "reference_cycle": "foreign_key_violated_by_seed",
    "duplicate_unique": "unique_violated_by_seed",
    "check_violated": "check_violated_by_seed",
}
# Нарушения значения колонки: конфликт называет колонку
_COLUMN_CODES = frozenset({"null_value", "check_violated"})
_TABLE = re.compile(r"^tables\[(\d+)\]")
_COLUMN = re.compile(r"^tables\[\d+\]\.rows\[\d+\]\.(\w+)$")


class SeedConflictChecker:
    """Реализация проверки принятого seed по модели попытки.

    Нарушение с кодом вне перечня `KINDS` переводится в вид, равный коду: принятый seed
    не должен давать таких нарушений, но и молча пропускать их нельзя.
    """

    def __init__(self, reader: SeedDraftReaderInterface, factory: SeedFactory) -> None:
        self._reader = reader
        self._factory = factory

    def check(
        self, seed_path: str, model: DataModel, dropped_columns: tuple[tuple[str, str], ...]
    ) -> tuple[SeedConflict, ...]:
        try:
            reading = self._reader.read(seed_path)
        except SeedNotFoundError:
            return ()
        except SeedUnreadableError as error:
            raise AcceptedSeedError(str(error)) from None
        draft = _without(reading.draft, frozenset(dropped_columns))
        violations = list(reading.violations)
        try:
            self._factory.create(model, draft)
        except SeedViolationError as error:
            violations += error.violations
        names = {table.position: table.name for table in reading.draft.tables}
        return tuple(_conflict(violation, names) for violation in violations)


def _without(draft: SeedDraft, dropped: frozenset[tuple[str, str]]) -> SeedDraft:
    """Черновик без ключей удалённых колонок."""
    return SeedDraft(
        tuple(
            SeedTableDraft(
                table.position,
                table.name,
                tuple(
                    RowDraft(tuple((k, v) for k, v in row.values if (table.name, k) not in dropped))
                    for row in table.rows
                ),
            )
            for table in draft.tables
        ),
        draft.excluded,
    )


def _conflict(violation: Violation, names: dict[int, str]) -> SeedConflict:
    table = _TABLE.match(violation.path)
    column = _COLUMN.match(violation.path) if violation.code in _COLUMN_CODES else None
    return SeedConflict(
        kind=KINDS.get(violation.code, violation.code),
        table=names.get(int(table.group(1)), "") if table else "",
        column=column.group(1) if column else None,
        path=violation.path,
        message=violation.message,
    )
