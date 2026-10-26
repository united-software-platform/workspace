"""Выходной контракт сценария отчёта: итог операции для LLM."""

from __future__ import annotations

from dataclasses import dataclass

from forge.operation.application.accepted_state import (
    AcceptedFiles,
    DeletedRow,
    DestructiveChange,
    ReconcileSummary,
    RollbackSummary,
    TableRowCounts,
)
from forge.operation.application.views import OperationView


@dataclass(frozen=True)
class AttemptReport:
    """Попытка в отчёте: вердикт, артефакты, итоги сверки и отката.

    Главный артефакт попытки — `model` у операции модели и `seed` у операции seed; другой — `None`.
    """

    number: int
    verdict: str | None
    backlog: str | None
    directory: str
    model: str | None
    changelog: str
    reconcile: ReconcileSummary | None
    rollback: RollbackSummary | None
    seed: str | None = None


@dataclass(frozen=True)
class BuildReportOutput:
    """Отчёт: операция, итоговые модель или seed и changelog, попытки, беклоги, файлы для коммита.

    `commit_files` — `None` у открытой операции; у закрытой — принятые файлы при `success`
    и каталоги следа: операции и беклогов начатых попыток. `destructive` — удаления итогового
    changelog: таблицы и колонки у операции модели, строки у операции seed; нет итогового
    changelog — пусто. `rows` — счётчики строк по таблицам итогового changelog данных операции
    seed; у операции модели — пусто.
    """

    operation: OperationView
    model: str | None
    changelog: str | None
    attempts: tuple[AttemptReport, ...]
    backlogs: tuple[str, ...]
    accepted: AcceptedFiles | None
    commit_files: tuple[str, ...] | None
    destructive: tuple[DestructiveChange | DeletedRow, ...] = ()
    seed: str | None = None
    rows: tuple[TableRowCounts, ...] = ()
