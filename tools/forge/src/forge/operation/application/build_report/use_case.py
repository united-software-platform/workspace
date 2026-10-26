"""Сценарий итогового отчёта операции."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol

from forge.operation.application.accepted_state import (
    AcceptedFiles,
    AcceptedStateInterface,
    AttemptResultsReaderInterface,
    DeletedRow,
    DestructiveChange,
    TableRowCounts,
)
from forge.operation.application.build_report.input import BuildReportInput
from forge.operation.application.build_report.output import AttemptReport, BuildReportOutput
from forge.operation.application.close_operation.use_case import accepted_files
from forge.operation.application.operation_reading import OperationReadRepositoryInterface
from forge.operation.application.restore import restore
from forge.operation.application.views import operation_view
from forge.operation.domain.factory import OperationFactory
from forge.operation.domain.operation import Operation, OperationKind, OperationStatus

MODEL = "model.yaml"
SEED = "seed.yaml"
CHANGELOG = "changelog.yaml"


class BuildReportUseCaseInterface(Protocol):
    """Собрать итоговый отчёт операции."""

    def execute(self, input: BuildReportInput) -> BuildReportOutput: ...


class BuildReportUseCase:
    """Отчёт без побочных эффектов: беклог, результаты попыток и принятые файлы.

    В отчёт входят попытки, которые начались: с вердиктом или порождённым беклогом.
    Итоговые модель (у операции seed — seed) и changelog — принятые файлы корня принятого
    состояния при `success`, иначе файлы последней начатой попытки. Файлы для коммита называются
    только у закрытой операции — `success`, `failure` или `abandoned`: след операции, а при
    `success` — и принятые файлы.
    """

    def __init__(
        self,
        reads: OperationReadRepositoryInterface,
        results: AttemptResultsReaderInterface,
        accepted: AcceptedStateInterface,
        factory: OperationFactory,
    ) -> None:
        self._reads = reads
        self._results = results
        self._accepted = accepted
        self._factory = factory

    def execute(self, input: BuildReportInput) -> BuildReportOutput:
        operation = restore(self._reads.get(input.operation_path), self._factory)
        seeding = operation.kind is OperationKind.SEED
        attempts = tuple(
            AttemptReport(
                number=a.number,
                verdict=a.verdict,
                backlog=a.backlog,
                directory=a.directory,
                model=None if seeding else f"{a.directory}/{MODEL}",
                changelog=f"{a.directory}/{CHANGELOG}",
                reconcile=self._results.reconcile(a.directory),
                rollback=self._results.rollback(a.directory),
                seed=f"{a.directory}/{SEED}" if seeding else None,
            )
            for a in operation.attempts
            if a.verdict is not None or a.backlog is not None
        )
        accepted = self._accepted_files(operation)
        final: AcceptedFiles | AttemptReport | None = accepted or (
            attempts[-1] if attempts else None
        )
        changelog = final.changelog if final is not None else None
        destructive: tuple[DestructiveChange | DeletedRow, ...] = ()
        rows: tuple[TableRowCounts, ...] = ()
        if changelog is not None and seeding:
            changes = self._results.data_changes(changelog)
            destructive, rows = changes.deleted, changes.tables
        elif changelog is not None:
            destructive = self._results.destructive(changelog)
        backlogs = (operation.path, *(a.backlog for a in attempts if a.backlog is not None))
        commit_files: tuple[str, ...] | None = None
        if operation.status.closed:
            trail = tuple(_directory(backlog) for backlog in backlogs)
            commit_files = (*_accepted_paths(accepted), *trail)
        return BuildReportOutput(
            operation=operation_view(operation),
            model=final.model if final is not None else None,
            changelog=changelog,
            attempts=attempts,
            backlogs=backlogs,
            accepted=accepted,
            commit_files=commit_files,
            destructive=destructive,
            seed=final.seed if final is not None else None,
            rows=rows,
        )

    def _accepted_files(self, operation: Operation) -> AcceptedFiles | None:
        if operation.status is not OperationStatus.SUCCESS:
            return None
        return accepted_files(self._accepted, operation)


def _accepted_paths(accepted: AcceptedFiles | None) -> tuple[str, ...]:
    """Принятые файлы для коммита: главный файл вида, changelog, `master.yaml`, изменённый seed."""
    if accepted is None:
        return ()
    paths: tuple[str | None, ...]
    if accepted.model is None:
        paths = (accepted.seed, accepted.changelog, accepted.master)
    else:
        paths = (accepted.model, accepted.changelog, accepted.master, accepted.seed)
    return tuple(path for path in paths if path is not None)


def _directory(backlog: str) -> str:
    """Каталог беклога в следе с завершающим `/`: коммитится целиком, с артефактами попыток."""
    return f"{PurePosixPath(backlog).parent.as_posix()}/"
