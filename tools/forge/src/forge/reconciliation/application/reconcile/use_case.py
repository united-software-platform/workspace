"""Сценарий сверки фактической схемы и журнала Liquibase с моделью попытки."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from forge.modeling.application.load_model.input import LoadModelInput
from forge.modeling.application.load_model.use_case import LoadModelUseCaseInterface
from forge.reconciliation.application.contracts import (
    ChangesetListReaderInterface,
    JournalRecordsReaderInterface,
    SchemaIntrospectorInterface,
)
from forge.reconciliation.application.reconcile.input import ReconcileInput
from forge.reconciliation.application.reconcile.output import DiscrepancyView, ReconcileOutput
from forge.reconciliation.domain.journal_check import JournalCheck
from forge.reconciliation.domain.schema_comparison import SchemaComparison
from forge.shared.application.result_writer import ResultWriterInterface
from forge.shared.application.settings import TargetDatabaseSettingsInterface

RECONCILE_RESULT = "reconcile.json"
SUCCESS = "success"
FAILURE = "failure"


class ReconcileUseCaseInterface(Protocol):
    """Сверить результат попытки."""

    def execute(self, input: ReconcileInput) -> ReconcileOutput: ...


@dataclass(frozen=True)
class ReconcileDependencies:
    """Контракты, через которые сценарий сверки обращается к окружению."""

    settings: TargetDatabaseSettingsInterface
    models: LoadModelUseCaseInterface
    changesets: ChangesetListReaderInterface
    schema: SchemaIntrospectorInterface
    journal: JournalRecordsReaderInterface
    writer: ResultWriterInterface


class ReconcileUseCase:
    """Перечень тестовых, модель, changelog, каталог и журнал, сравнение, `reconcile.json`.

    Ошибки окружения и входных файлов — исключения контрактов; `reconcile.json` тогда
    не пишется, чтобы беклог не счёл сверку выполненной.
    """

    def __init__(self, dependencies: ReconcileDependencies) -> None:
        self._deps = dependencies

    def execute(self, input: ReconcileInput) -> ReconcileOutput:
        target = self._deps.settings.target()
        self._deps.settings.allowlist().require(target)
        model = self._deps.models.execute(LoadModelInput(input.model_path)).model
        expected = self._deps.changesets.read(input.changelog_path)
        actual = self._deps.schema.read(target)
        records = self._deps.journal.records(target)

        discrepancies = SchemaComparison().compare(model, actual) + JournalCheck().compare(
            expected, records
        )
        views = tuple(
            DiscrepancyView(d.kind, d.table, d.column, d.changeset, d.expected, d.actual, d.message)
            for d in discrepancies
        )
        output = ReconcileOutput(
            result_path=str(PurePosixPath(input.changelog_path).parent / RECONCILE_RESULT),
            model_path=input.model_path,
            changelog_path=input.changelog_path,
            database=str(target),
            verdict=FAILURE if views else SUCCESS,
            discrepancies=views,
        )
        self._deps.writer.write(output.result_path, reconcile_document(output))
        return output


def reconcile_document(output: ReconcileOutput) -> dict[str, object]:
    """Документ `reconcile.json` и ответа команды."""
    return {
        "model": output.model_path,
        "changelog": output.changelog_path,
        "database": output.database,
        "verdict": output.verdict,
        "discrepancies": [
            {
                "kind": d.kind,
                "table": d.table,
                "column": d.column,
                "changeset": d.changeset,
                "expected": d.expected,
                "actual": d.actual,
                "message": d.message,
            }
            for d in output.discrepancies
        ],
    }
