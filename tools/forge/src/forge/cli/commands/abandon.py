"""Команда `forge abandon --operation <беклог> --reason <текст>`: отказ от открытой операции."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from forge.cli.commands.operation_support import (
    operation_payload,
    read_repository,
    write_repository,
)
from forge.cli.commands.rollback import (
    ROLLBACK_ERRORS,
    rollback_environment_error,
)
from forge.cli.commands.rollback import (
    build_use_case as build_rollback_use_case,
)
from forge.cli.contract import ExitCode, emit, environment_error
from forge.migration.application.rollback_attempt.input import RollbackAttemptInput
from forge.migration.application.rollback_attempt.use_case import RollbackAttemptUseCaseInterface
from forge.operation.application.abandon_operation.input import AbandonOperationInput
from forge.operation.application.abandon_operation.output import (
    AbandonRefusedError,
    AttemptRollbackView,
)
from forge.operation.application.abandon_operation.use_case import (
    AbandonOperationUseCase,
    AbandonOperationUseCaseInterface,
)
from forge.operation.application.operation_reading import OperationUnavailableError
from forge.operation.domain.factory import OperationFactory
from forge.operation.infrastructure.attempt_results import JsonAttemptResultsReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `abandon`."""
    parser = subparsers.add_parser("abandon", add_help=False)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--reason", required=True)
    parser.set_defaults(handler=run)


class RollbackDiscarder:
    """Откат при отказе поверх сценария отката Миграций — связь контекстов в точке сборки.

    Сценарий отката собирается при первом откате: отказ без начатых попыток не требует
    ни настроек БД, ни раннера.
    """

    def __init__(self, build: Callable[[], RollbackAttemptUseCaseInterface]) -> None:
        self._build = build
        self._use_case: RollbackAttemptUseCaseInterface | None = None

    def discard(self, operation_path: str, attempt: int) -> bool:
        if self._use_case is None:
            self._use_case = self._build()
        output = self._use_case.execute(RollbackAttemptInput(operation_path, attempt, discard=True))
        return output.verified


def build_use_case(
    rollback: Callable[[], RollbackAttemptUseCaseInterface] = build_rollback_use_case,
) -> AbandonOperationUseCaseInterface:
    """Собрать сценарий: беклоги следа, результаты попыток, откат через сценарий Миграций."""
    return AbandonOperationUseCase(
        read_repository(),
        write_repository(),
        JsonAttemptResultsReader(),
        RollbackDiscarder(rollback),
        OperationFactory(),
    )


def _rollbacks(views: tuple[AttemptRollbackView, ...]) -> list[dict[str, object]]:
    return [
        {
            "attempt": view.attempt,
            "result": view.result,
            "verified": view.verified,
            "performed": view.performed,
        }
        for view in views
    ]


def run(args: argparse.Namespace, use_case: AbandonOperationUseCaseInterface | None = None) -> int:
    """`0` — брошена сейчас или раньше, `1` — закрыта либо откат не подтверждён, `2` — окружение."""
    operation: str = args.operation
    try:
        output = (use_case or build_use_case()).execute(
            AbandonOperationInput(operation, args.reason)
        )
    except OperationUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=operation)
    except ROLLBACK_ERRORS as error:
        return rollback_environment_error(error, operation)
    except AbandonRefusedError as error:
        emit(
            {
                "operation": operation,
                "refused": str(error),
                "rollbacks": _rollbacks(error.rollbacks),
            }
        )
        return ExitCode.FAILURE
    emit(
        {
            "operation": operation_payload(output.operation),
            "rollbacks": _rollbacks(output.rollbacks),
            "changed": output.changed,
        }
    )
    return ExitCode.SUCCESS
