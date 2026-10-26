"""Команда `forge rollback --operation <беклог> --attempt <N>`: откат неуспешной попытки."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from forge.cli.contract import ExitCode, emit, environment_error
from forge.migration.application.liquibase_gateway import GatewayUnavailableError
from forge.migration.application.operation_record import OperationRecordUnavailableError
from forge.migration.application.rollback_attempt.input import RollbackAttemptInput
from forge.migration.application.rollback_attempt.use_case import (
    RollbackAttemptUseCase,
    RollbackAttemptUseCaseInterface,
    RollbackDependencies,
)
from forge.migration.infrastructure.liquibase_changelog import LiquibaseYamlChangelogReader
from forge.migration.infrastructure.operation_record_reader import (
    FrontmatterOperationRecordReader,
)
from forge.migration.infrastructure.postgres import (
    PsycopgDatabaseRecreator,
    PsycopgJournalReader,
    PsycopgRowProbe,
    PsycopgSchemaProbe,
)
from forge.migration.infrastructure.runner_gateway import RunnerLiquibaseGateway
from forge.shared.application.settings import (
    DatabaseUnavailableError,
    SettingsUnavailableError,
)
from forge.shared.domain.target_database import DatabaseNotAllowedError
from forge.shared.infrastructure.json_result_writer import JsonResultWriter
from forge.shared.infrastructure.postgres import PostgresConnector
from forge.shared.infrastructure.runner import runner_settings
from forge.shared.infrastructure.settings import EnvironmentSettings

ATTEMPTS = (1, 2, 3)
ACCEPTED_MASTER = "changelog/master.yaml"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `rollback`."""
    parser = subparsers.add_parser("rollback", add_help=False)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--attempt", required=True, type=int, choices=ATTEMPTS)
    parser.set_defaults(handler=run)


def accepted_master(settings: EnvironmentSettings) -> str:
    """Принятый `master.yaml` корня принятого состояния — для наката на запасном пути."""
    return (settings.accepted_root() / ACCEPTED_MASTER).as_posix()


def build_use_case(accepted_master_path: str | None = None) -> RollbackAttemptUseCaseInterface:
    """Собрать сценарий: окружение процесса, `psycopg`, шлюз через раннер."""
    settings = EnvironmentSettings(os.environ)
    master = accepted_master_path or accepted_master(settings)
    connector = PostgresConnector(settings.credentials())
    return RollbackAttemptUseCase(
        RollbackDependencies(
            operations=FrontmatterOperationRecordReader(),
            settings=settings,
            changelogs=LiquibaseYamlChangelogReader(),
            journal=PsycopgJournalReader(connector),
            schema=PsycopgSchemaProbe(connector),
            rows=PsycopgRowProbe(connector),
            recreator=PsycopgDatabaseRecreator(connector),
            gateway=RunnerLiquibaseGateway(Path.cwd(), runner_settings(os.environ)),
            writer=JsonResultWriter(),
        ),
        master,
    )


# Ошибки окружения сценария отката: общие для `forge rollback` и отката при `forge abandon`
ROLLBACK_ERRORS = (
    OperationRecordUnavailableError,
    SettingsUnavailableError,
    DatabaseNotAllowedError,
    DatabaseUnavailableError,
    GatewayUnavailableError,
)


def rollback_environment_error(error: Exception, operation: str) -> int:
    """Ответ и код `2` на ошибку окружения из `ROLLBACK_ERRORS`."""
    if isinstance(error, OperationRecordUnavailableError):
        return environment_error("operation_unavailable", str(error), operation=operation)
    if isinstance(error, SettingsUnavailableError):
        return environment_error("settings_unavailable", str(error))
    if isinstance(error, DatabaseNotAllowedError):
        return environment_error("database_not_allowed", str(error))
    if isinstance(error, DatabaseUnavailableError):
        return environment_error("database_unavailable", str(error))
    if isinstance(error, GatewayUnavailableError):
        return environment_error(error.kind, str(error))
    raise error


def run(args: argparse.Namespace, use_case: RollbackAttemptUseCaseInterface | None = None) -> int:
    """`0` — возврат подтверждён или откатывать нечего, `1` — не подтверждён, `2` — окружение."""
    operation: str = args.operation
    try:
        output = (use_case or build_use_case()).execute(
            RollbackAttemptInput(operation, args.attempt)
        )
    except ROLLBACK_ERRORS as error:
        return rollback_environment_error(error, operation)
    emit(
        {
            "attempt": output.attempt,
            "verdict": output.verdict,
            "action": output.action,
            "rolled_back": output.rolled_back,
            "result": output.result_path,
            "fallback_reason": output.fallback_reason,
            "verified": output.verified,
        }
    )
    return ExitCode.SUCCESS if output.verified else ExitCode.FAILURE
