"""Команда `forge reconcile-seed --seed <seed> --changelog <changelog>`: сверка попытки seed."""

from __future__ import annotations

import argparse
import os

from forge.cli.contract import ExitCode, emit, environment_error
from forge.modeling.application.load_model.use_case import InvalidModelError, LoadModelUseCase
from forge.modeling.application.model_reading import ModelUnreadableError
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.infrastructure.yaml_reader import YamlModelDraftReader
from forge.reconciliation.application.contracts import ChangelogUnreadableError
from forge.reconciliation.infrastructure.changeset_list_reader import YamlChangesetListReader
from forge.reconciliation.infrastructure.postgres_introspection import PsycopgJournalRecordsReader
from forge.seeding.application.accepted_seed import AcceptedSeedError
from forge.seeding.application.reconcile_seed.input import ReconcileSeedInput
from forge.seeding.application.reconcile_seed.use_case import (
    SUCCESS,
    ReconcileSeedDependencies,
    ReconcileSeedUseCase,
    ReconcileSeedUseCaseInterface,
    SeedInvalidError,
    reconcile_seed_document,
)
from forge.seeding.application.seed_reading import SeedUnreadableError
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.infrastructure.postgres_rows import PsycopgTableRowsReader
from forge.seeding.infrastructure.yaml_reader import YamlSeedDraftReader
from forge.shared.application.settings import DatabaseUnavailableError, SettingsUnavailableError
from forge.shared.domain.target_database import DatabaseNotAllowedError
from forge.shared.infrastructure.json_result_writer import JsonResultWriter
from forge.shared.infrastructure.postgres import PostgresConnector
from forge.shared.infrastructure.settings import EnvironmentSettings

ACCEPTED_MODEL = "model.yaml"
ACCEPTED_SEED = "seed.yaml"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `reconcile-seed`."""
    parser = subparsers.add_parser("reconcile-seed", add_help=False)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--changelog", required=True)
    # Без `--accepted-seed` и `--model` они берутся из корня принятого состояния
    parser.add_argument("--accepted-seed")
    parser.add_argument("--model")
    parser.set_defaults(handler=run)


def build_use_case() -> ReconcileSeedUseCaseInterface:
    """Собрать сценарий: окружение процесса, чтение строк и журнала `psycopg`, разборщики YAML."""
    settings = EnvironmentSettings(os.environ)
    connector = PostgresConnector(settings.credentials())
    return ReconcileSeedUseCase(
        ReconcileSeedDependencies(
            settings=settings,
            models=LoadModelUseCase(YamlModelDraftReader(), DataModelFactory()),
            seeds=YamlSeedDraftReader(),
            changesets=YamlChangesetListReader(),
            rows=PsycopgTableRowsReader(connector),
            journal=PsycopgJournalRecordsReader(connector),
            writer=JsonResultWriter(),
            factory=SeedFactory(),
        )
    )


def run(args: argparse.Namespace, use_case: ReconcileSeedUseCaseInterface | None = None) -> int:
    """`0` — расхождений нет, `1` — есть, `2` — окружение или входные файлы."""
    seed_path: str = args.seed
    try:
        accepted_seed = args.accepted_seed or _accepted(ACCEPTED_SEED)
        model = args.model or _accepted(ACCEPTED_MODEL)
    except SettingsUnavailableError as error:
        return environment_error("accepted_root_invalid", str(error), seed=seed_path)
    request = ReconcileSeedInput(
        seed_path,
        args.changelog,
        accepted_seed,
        model,
        missing_model_as_empty=args.model is None,
    )
    try:
        output = (use_case or build_use_case()).execute(request)
    except SettingsUnavailableError as error:
        return environment_error("settings_unavailable", str(error))
    except DatabaseNotAllowedError as error:
        return environment_error("database_not_allowed", str(error))
    except DatabaseUnavailableError as error:
        return environment_error("database_unavailable", str(error))
    except ModelUnreadableError as error:
        return environment_error("model_unreadable", str(error), model=error.path)
    except InvalidModelError as error:
        return environment_error(
            "model_invalid",
            f"{error}; нарушения модели перечисляет forge validate --model {error.path}",
            model=error.path,
        )
    except SeedUnreadableError as error:
        return environment_error("seed_unreadable", str(error), seed=error.path)
    except SeedInvalidError as error:
        return environment_error(
            "seed_invalid",
            f"{error}; нарушения перечисляет forge validate-seed --seed {error.path}",
            seed=error.path,
        )
    except AcceptedSeedError as error:
        return environment_error("accepted_seed_invalid", str(error), accepted_seed=accepted_seed)
    except ChangelogUnreadableError as error:
        return environment_error("changelog_unreadable", str(error), changelog=args.changelog)
    emit(reconcile_seed_document(output))
    return ExitCode.SUCCESS if output.verdict == SUCCESS else ExitCode.FAILURE


def _accepted(name: str) -> str:
    return (EnvironmentSettings(os.environ).accepted_root() / name).as_posix()
