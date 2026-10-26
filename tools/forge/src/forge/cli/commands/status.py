"""Команда `forge status --operation <беклог> | --latest`: статус операции и проверка среды."""

from __future__ import annotations

import argparse
import os

from forge.cli.commands.operation_support import operation_payload, read_repository
from forge.cli.contract import ExitCode, emit, environment_error
from forge.operation.application.get_status.input import GetStatusInput
from forge.operation.application.get_status.use_case import (
    GetStatusUseCase,
    GetStatusUseCaseInterface,
)
from forge.operation.application.operation_reading import (
    OperationUnavailableError,
    SeveralOpenOperationsError,
)
from forge.operation.domain.factory import OperationFactory
from forge.operation.infrastructure.environment_probe import EnvironmentProbe


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `status`."""
    parser = subparsers.add_parser("status", add_help=False)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--operation")
    target.add_argument("--latest", action="store_true")
    parser.set_defaults(handler=run)


def build_use_case() -> GetStatusUseCaseInterface:
    return GetStatusUseCase(read_repository(), EnvironmentProbe(os.environ), OperationFactory())


def run(args: argparse.Namespace, use_case: GetStatusUseCaseInterface | None = None) -> int:
    """`0` — среда в порядке, `2` — проверка среды не пройдена или беклог не прочитать."""
    operation: str | None = args.operation
    try:
        output = (use_case or build_use_case()).execute(GetStatusInput(operation))
    except OperationUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=operation)
    except SeveralOpenOperationsError as error:
        return environment_error(
            "several_open_operations", str(error), operations=list(error.paths)
        )
    emit(
        {
            "operation": operation_payload(output.operation) if output.operation else None,
            "environment_ok": output.environment_ok,
            "environment": [
                {"check": c.name, "passed": c.passed, "detail": c.detail} for c in output.checks
            ],
        }
    )
    return ExitCode.SUCCESS if output.environment_ok else ExitCode.ENVIRONMENT_ERROR
