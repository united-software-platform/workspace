"""Команда `forge resume --operation <беклог>`: продолжение операции, согласие на удаления."""

from __future__ import annotations

import argparse

from forge.cli.commands.operation_support import (
    operation_payload,
    read_repository,
    write_repository,
)
from forge.cli.contract import ExitCode, emit, environment_error
from forge.operation.application.change_status.input import ResumeOperationInput
from forge.operation.application.change_status.use_case import (
    ResumeOperationUseCase,
    ResumeOperationUseCaseInterface,
)
from forge.operation.application.operation_reading import OperationUnavailableError
from forge.operation.domain.factory import OperationFactory
from forge.operation.domain.operation import OperationTransitionError


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `resume`."""
    parser = subparsers.add_parser("resume", add_help=False)
    parser.add_argument("--operation", required=True)
    # Согласие на удаления остановленной операции в режиме auto; снять его нельзя
    parser.add_argument("--allow-drop", action="store_true")
    parser.set_defaults(handler=run)


def build_use_case() -> ResumeOperationUseCaseInterface:
    return ResumeOperationUseCase(read_repository(), write_repository(), OperationFactory())


def run(args: argparse.Namespace, use_case: ResumeOperationUseCaseInterface | None = None) -> int:
    """`0` — операция продолжена, `1` — не остановлена или согласие не применимо, `2` — беклог."""
    request = ResumeOperationInput(args.operation, getattr(args, "allow_drop", False))
    try:
        view = (use_case or build_use_case()).execute(request)
    except OperationUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=args.operation)
    except OperationTransitionError as error:
        emit({"operation": args.operation, "refused": str(error)})
        return ExitCode.FAILURE
    emit({"operation": operation_payload(view)})
    return ExitCode.SUCCESS
