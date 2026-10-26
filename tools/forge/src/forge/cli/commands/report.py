"""Команда `forge report --operation <беклог>`: итоговый отчёт операции для LLM."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import Any

from forge.cli.commands.operation_support import (
    accepted_state,
    operation_payload,
    read_repository,
)
from forge.cli.contract import ExitCode, emit, environment_error
from forge.operation.application.accepted_state import DeletedRow, DestructiveChange
from forge.operation.application.build_report.input import BuildReportInput
from forge.operation.application.build_report.output import BuildReportOutput
from forge.operation.application.build_report.use_case import (
    BuildReportUseCase,
    BuildReportUseCaseInterface,
)
from forge.operation.application.operation_reading import OperationUnavailableError
from forge.operation.domain.factory import OperationFactory
from forge.operation.infrastructure.attempt_results import JsonAttemptResultsReader
from forge.shared.application.settings import SettingsUnavailableError

FAILURE = "failure"
ABANDONED = "abandoned"
SUCCESS_HINT = (
    "Принятое состояние и след операции не закоммичены: закоммитьте эти файлы и каталоги, "
    "указав код и номер задачи в сообщении коммита"
)
FAILURE_HINT = (
    "Принятое состояние не изменилось; след операции объясняет почему: закоммитьте эти каталоги, "
    "указав код и номер задачи в сообщении коммита"
)
ABANDONED_HINT = (
    "Операция брошена, принятое состояние не изменилось; причина — в stop_reason: закоммитьте "
    "эти каталоги, указав код и номер задачи в сообщении коммита"
)
HINTS = {FAILURE: FAILURE_HINT, ABANDONED: ABANDONED_HINT}


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `report`."""
    parser = subparsers.add_parser("report", add_help=False)
    parser.add_argument("--operation", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> BuildReportUseCaseInterface:
    return BuildReportUseCase(
        read_repository(),
        JsonAttemptResultsReader(),
        accepted_state(),
        OperationFactory(),
    )


def run(args: argparse.Namespace, use_case: BuildReportUseCaseInterface | None = None) -> int:
    """`0` — отчёт собран, `1` — операция закрыта со статусом `failure`, `2` — беклог или корень."""
    try:
        output = (use_case or build_use_case()).execute(BuildReportInput(args.operation))
    except SettingsUnavailableError as error:
        return environment_error("accepted_root_invalid", str(error), operation=args.operation)
    except OperationUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=args.operation)
    emit(report_payload(output))
    return ExitCode.FAILURE if output.operation.status == FAILURE else ExitCode.SUCCESS


def report_payload(output: BuildReportOutput) -> dict[str, Any]:
    """Отчёт в ответе команды."""
    accepted = output.accepted
    return {
        "operation": operation_payload(output.operation),
        "model": output.model,
        "seed": output.seed,
        "changelog": output.changelog,
        "attempts": [
            {
                "number": a.number,
                "verdict": a.verdict,
                "backlog": a.backlog,
                "directory": a.directory,
                "model": a.model,
                "seed": a.seed,
                "changelog": a.changelog,
                "reconcile": asdict(a.reconcile) if a.reconcile else None,
                "rollback": asdict(a.rollback) if a.rollback else None,
            }
            for a in output.attempts
        ],
        "backlogs": list(output.backlogs),
        "accepted": asdict(accepted) if accepted else None,
        "rows": [asdict(counts) for counts in output.rows],
        "destructive": [_destructive(change) for change in output.destructive],
        "commit": (
            {
                "files": list(output.commit_files),
                "hint": HINTS.get(output.operation.status, SUCCESS_HINT),
            }
            if output.commit_files is not None
            else None
        ),
    }


def _destructive(change: DestructiveChange | DeletedRow) -> dict[str, Any]:
    """Удаление в отчёте: таблица и колонка — у модели, таблица и первичный ключ строки — у seed."""
    if isinstance(change, DeletedRow):
        return {"table": change.table, "key": dict(change.key)}
    return asdict(change)
