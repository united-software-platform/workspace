"""Команда `forge close --operation <беклог>`: закрытие операции и принятие её файлов в корень."""

from __future__ import annotations

import argparse

from forge.cli.commands.operation_support import (
    accepted_state,
    operation_payload,
    read_repository,
    write_repository,
)
from forge.cli.contract import ExitCode, emit, environment_error
from forge.operation.application.accepted_state import AcceptanceError
from forge.operation.application.close_operation.input import CloseOperationInput
from forge.operation.application.close_operation.use_case import (
    CloseOperationUseCase,
    CloseOperationUseCaseInterface,
)
from forge.operation.application.operation_reading import OperationUnavailableError
from forge.operation.domain.factory import OperationFactory
from forge.operation.domain.operation import OperationTransitionError
from forge.operation.infrastructure.attempt_results import JsonAttemptResultsReader
from forge.shared.application.settings import SettingsUnavailableError


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `close`."""
    parser = subparsers.add_parser("close", add_help=False)
    parser.add_argument("--operation", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> CloseOperationUseCaseInterface:
    """Собрать сценарий: беклоги следа, результаты попыток, корень принятого состояния."""
    return CloseOperationUseCase(
        read_repository(),
        write_repository(),
        JsonAttemptResultsReader(),
        accepted_state(),
        OperationFactory(),
    )


def run(args: argparse.Namespace, use_case: CloseOperationUseCaseInterface | None = None) -> int:
    """`0` — операция закрыта, `1` — закрывать рано, `2` — беклог или корень недоступны."""
    try:
        output = (use_case or build_use_case()).execute(CloseOperationInput(args.operation))
    except SettingsUnavailableError as error:
        return environment_error("accepted_root_invalid", str(error), operation=args.operation)
    except OperationUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=args.operation)
    except AcceptanceError as error:
        return environment_error("acceptance_failed", str(error), operation=args.operation)
    except OperationTransitionError as error:
        emit({"operation": args.operation, "refused": str(error)})
        return ExitCode.FAILURE
    accepted = output.accepted
    emit(
        {
            "operation": operation_payload(output.operation),
            "accepted_attempt": output.accepted_attempt,
            "accepted": (
                {
                    "model": accepted.model,
                    "seed": accepted.seed,
                    "changelog": accepted.changelog,
                    "master": accepted.master,
                }
                if accepted
                else None
            ),
            "changed": output.changed,
        }
    )
    return ExitCode.SUCCESS
