"""Сценарий сверки строк таблиц seed и журнала Liquibase с seed попытки."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from forge.modeling.application.load_model.input import LoadModelInput
from forge.modeling.application.load_model.use_case import LoadModelUseCaseInterface
from forge.modeling.domain.data_model import DataModel
from forge.modeling.domain.violation import Violation
from forge.reconciliation.application.contracts import (
    ChangesetListReaderInterface,
    JournalRecordsReaderInterface,
)
from forge.reconciliation.domain.journal_check import JournalCheck
from forge.seeding.application.accepted_seed import load_accepted_seed
from forge.seeding.application.reconcile_seed.input import ReconcileSeedInput
from forge.seeding.application.reconcile_seed.output import (
    ReconcileSeedOutput,
    SeedDiscrepancyView,
)
from forge.seeding.application.seed_reading import SeedDraftReaderInterface
from forge.seeding.application.table_rows import TableRowsReaderInterface
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.domain.rows_comparison import SeedRowsComparison
from forge.seeding.domain.seed import Seed, SeedViolationError
from forge.shared.application.result_writer import ResultWriterInterface
from forge.shared.application.settings import TargetDatabaseSettingsInterface

RECONCILE_RESULT = "reconcile.json"
SUCCESS = "success"
FAILURE = "failure"


class SeedInvalidError(Exception):
    """Seed попытки не проходит проверку `forge validate-seed`: вердикта по нему нет."""

    def __init__(self, path: str, violations: tuple[Violation, ...]) -> None:
        first = violations[0]
        super().__init__(
            f"seed попытки {path} не проходит проверку по модели, нарушений: {len(violations)}; "
            f"первое — {first.path}: {first.message}"
        )
        self.path = path
        self.violations = violations


class ReconcileSeedUseCaseInterface(Protocol):
    """Сверить результат попытки seed."""

    def execute(self, input: ReconcileSeedInput) -> ReconcileSeedOutput: ...


@dataclass(frozen=True)
class ReconcileSeedDependencies:
    """Контракты, через которые сценарий сверки seed обращается к окружению.

    Чтение changelog и журнала — контракты контекста «Сверка»: проверка журнала одна
    для сверки модели и сверки seed.
    """

    settings: TargetDatabaseSettingsInterface
    models: LoadModelUseCaseInterface
    seeds: SeedDraftReaderInterface
    changesets: ChangesetListReaderInterface
    rows: TableRowsReaderInterface
    journal: JournalRecordsReaderInterface
    writer: ResultWriterInterface
    factory: SeedFactory


class ReconcileSeedUseCase:
    """Перечень тестовых, модель, оба seed, changelog, строки и журнал, сравнение, `reconcile.json`.

    Все файлы читаются и проверяются до подключения к БД. Ошибки окружения и входных
    файлов — исключения: `SettingsUnavailableError`, `DatabaseNotAllowedError`,
    `DatabaseUnavailableError`, `ModelUnreadableError`, `InvalidModelError`,
    `SeedUnreadableError`, `SeedInvalidError`, `AcceptedSeedError`, `ChangelogUnreadableError`;
    `reconcile.json` тогда не пишется, чтобы беклог не счёл сверку выполненной.
    """

    def __init__(self, dependencies: ReconcileSeedDependencies) -> None:
        self._deps = dependencies

    def execute(self, input: ReconcileSeedInput) -> ReconcileSeedOutput:
        target = self._deps.settings.target()
        self._deps.settings.allowlist().require(target)
        model = self._deps.models.execute(
            LoadModelInput(input.model_path, missing_as_empty=input.missing_model_as_empty)
        ).model
        attempt = self._attempt(model, input.seed_path)
        accepted = load_accepted_seed(
            self._deps.seeds, self._deps.factory, model, input.accepted_seed_path
        )
        expected = self._deps.changesets.read(input.changelog_path)
        removed = tuple(t.table for t in accepted.tables if not attempt.has_table(t.name))

        actual = self._deps.rows.rows(target, (*(t.table for t in attempt.tables), *removed))
        records = self._deps.journal.records(target)

        discrepancies = SeedRowsComparison().compare(
            attempt, removed, actual
        ) + JournalCheck().compare(expected, records)
        views = tuple(
            SeedDiscrepancyView(
                d.kind, d.table, d.key, d.column, d.changeset, d.expected, d.actual, d.message
            )
            for d in discrepancies
        )
        output = ReconcileSeedOutput(
            result_path=str(PurePosixPath(input.changelog_path).parent / RECONCILE_RESULT),
            seed_path=input.seed_path,
            changelog_path=input.changelog_path,
            database=str(target),
            verdict=FAILURE if views else SUCCESS,
            discrepancies=views,
        )
        self._deps.writer.write(output.result_path, reconcile_seed_document(output))
        return output

    def _attempt(self, model: DataModel, path: str) -> Seed:
        reading = self._deps.seeds.read(path)
        violations = reading.violations
        try:
            seed = self._deps.factory.create(model, reading.draft)
        except SeedViolationError as error:
            violations = (*violations, *error.violations)
        if violations:
            raise SeedInvalidError(path, violations)
        return seed


def reconcile_seed_document(output: ReconcileSeedOutput) -> dict[str, object]:
    """Документ `reconcile.json` и ответа команды сверки seed."""
    return {
        "seed": output.seed_path,
        "changelog": output.changelog_path,
        "database": output.database,
        "verdict": output.verdict,
        "discrepancies": [
            {
                "kind": d.kind,
                "table": d.table,
                "key": dict(d.key) if d.key is not None else None,
                "column": d.column,
                "changeset": d.changeset,
                "expected": d.expected,
                "actual": d.actual,
                "message": d.message,
            }
            for d in output.discrepancies
        ],
    }
