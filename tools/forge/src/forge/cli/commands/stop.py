"""Команда `forge stop --operation <беклог> --reason <текст>`: остановка операции."""

from __future__ import annotations

import argparse

from forge.cli.commands.operation_support import (
    operation_payload,
    read_repository,
    write_repository,
)
from forge.cli.contract import ExitCode, emit, environment_error
from forge.operation.application.change_status.input import StopOperationInput
from forge.operation.application.change_status.use_case import (
    StopOperationUseCase,
    StopOperationUseCaseInterface,
)
from forge.operation.application.operation_reading import OperationUnavailableError
from forge.operation.domain.factory import OperationFactory
from forge.operation.domain.operation import OperationTransitionError


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `stop`."""
    parser = subparsers.add_parser("stop", add_help=False)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--reason", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> StopOperationUseCaseInterface:
    return StopOperationUseCase(read_repository(), write_repository(), OperationFactory())


def run(args: argparse.Namespace, use_case: StopOperationUseCaseInterface | None = None) -> int:
    """`0` — операция остановлена, `1` — операция закрыта, `2` — беклог не прочитать."""
    try:
        view = (use_case or build_use_case()).execute(
            StopOperationInput(args.operation, args.reason)
        )
    except OperationUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=args.operation)
    except OperationTransitionError as error:
        emit({"operation": args.operation, "refused": str(error)})
        return ExitCode.FAILURE
    emit({"operation": operation_payload(view)})
    return ExitCode.SUCCESS
