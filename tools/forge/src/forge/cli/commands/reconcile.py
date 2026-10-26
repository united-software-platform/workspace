"""Команда `forge reconcile --model <модель> --changelog <changelog>`: сверка попытки."""

from __future__ import annotations

import argparse
import os

from forge.cli.contract import ExitCode, emit, environment_error
from forge.modeling.application.load_model.use_case import InvalidModelError, LoadModelUseCase
from forge.modeling.application.model_reading import ModelUnreadableError
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.infrastructure.yaml_reader import YamlModelDraftReader
from forge.reconciliation.application.contracts import ChangelogUnreadableError
from forge.reconciliation.application.reconcile.input import ReconcileInput
from forge.reconciliation.application.reconcile.use_case import (
    SUCCESS,
    ReconcileDependencies,
    ReconcileUseCase,
    ReconcileUseCaseInterface,
    reconcile_document,
)
from forge.reconciliation.infrastructure.changeset_list_reader import YamlChangesetListReader
from forge.reconciliation.infrastructure.postgres_introspection import (
    PsycopgJournalRecordsReader,
    PsycopgSchemaIntrospector,
)
from forge.shared.application.settings import DatabaseUnavailableError, SettingsUnavailableError
from forge.shared.domain.target_database import DatabaseNotAllowedError
from forge.shared.infrastructure.json_result_writer import JsonResultWriter
from forge.shared.infrastructure.postgres import PostgresConnector
from forge.shared.infrastructure.settings import EnvironmentSettings


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `reconcile`."""
    parser = subparsers.add_parser("reconcile", add_help=False)
    parser.add_argument("--model", required=True)
    parser.add_argument("--changelog", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> ReconcileUseCaseInterface:
    """Собрать сценарий: окружение процесса, интроспекция `psycopg`, разборщики YAML."""
    settings = EnvironmentSettings(os.environ)
    connector = PostgresConnector(settings.credentials())
    return ReconcileUseCase(
        ReconcileDependencies(
            settings=settings,
            models=LoadModelUseCase(YamlModelDraftReader(), DataModelFactory()),
            changesets=YamlChangesetListReader(),
            schema=PsycopgSchemaIntrospector(connector),
            journal=PsycopgJournalRecordsReader(connector),
            writer=JsonResultWriter(),
        )
    )


def run(args: argparse.Namespace, use_case: ReconcileUseCaseInterface | None = None) -> int:
    """`0` — расхождений нет, `1` — есть, `2` — окружение или входные файлы."""
    try:
        output = (use_case or build_use_case()).execute(ReconcileInput(args.model, args.changelog))
    except SettingsUnavailableError as error:
        return environment_error("settings_unavailable", str(error))
    except DatabaseNotAllowedError as error:
        return environment_error("database_not_allowed", str(error))
    except DatabaseUnavailableError as error:
        return environment_error("database_unavailable", str(error))
    except ModelUnreadableError as error:
        return environment_error("model_unreadable", str(error), model=error.path)
    except InvalidModelError as error:
        return environment_error("model_invalid", str(error), model=error.path)
    except ChangelogUnreadableError as error:
        return environment_error("changelog_unreadable", str(error), changelog=args.changelog)
    emit(reconcile_document(output))
    return ExitCode.SUCCESS if output.verdict == SUCCESS else ExitCode.FAILURE
