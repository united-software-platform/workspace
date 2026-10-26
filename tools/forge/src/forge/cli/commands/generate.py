"""Команда `forge generate`: changelog из разницы моделей."""

from __future__ import annotations

import argparse
import os
from pathlib import PurePosixPath
from typing import Any

from forge.cli.contract import ExitCode, emit, environment_error
from forge.migration.application.generate_changelog.input import GenerateChangelogInput
from forge.migration.application.generate_changelog.output import GenerateChangelogOutput
from forge.migration.application.generate_changelog.use_case import (
    AcceptedModelError,
    DropNotAllowedError,
    GenerateChangelogUseCase,
    GenerateChangelogUseCaseInterface,
)
from forge.migration.application.operation_record import OperationRecordUnavailableError
from forge.migration.application.seed_conflicts import AcceptedSeedError
from forge.migration.domain.model_diff import ModelDiff
from forge.migration.infrastructure.liquibase_changelog import (
    LiquibaseConstraintNaming,
    LiquibaseYamlChangelogWriter,
)
from forge.migration.infrastructure.operation_record_reader import (
    FrontmatterOperationRecordReader,
)
from forge.migration.infrastructure.seed_conflicts import SeedConflictChecker
from forge.modeling.application.load_model.use_case import LoadModelUseCase
from forge.modeling.application.model_reading import ModelUnreadableError
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.infrastructure.yaml_reader import YamlModelDraftReader
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.infrastructure.yaml_reader import YamlSeedDraftReader
from forge.shared.application.settings import SettingsUnavailableError
from forge.shared.infrastructure.settings import EnvironmentSettings

ACCEPTED_MODEL = "model.yaml"
ACCEPTED_SEED = "seed.yaml"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `generate`."""
    parser = subparsers.add_parser("generate", add_help=False)
    parser.add_argument("--model", required=True)
    # Без `--accepted` принятая модель берётся из корня принятого состояния
    parser.add_argument("--accepted")
    # Без `--accepted-seed` принятый seed лежит рядом с принятой моделью
    parser.add_argument("--accepted-seed")
    parser.add_argument("--operation", required=True)
    parser.add_argument("--out", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> GenerateChangelogUseCaseInterface:
    """Собрать сценарий с чтением беклога, загрузкой моделей, проверкой принятого seed
    и записью YAML Liquibase."""
    return GenerateChangelogUseCase(
        FrontmatterOperationRecordReader(),
        LoadModelUseCase(YamlModelDraftReader(), DataModelFactory()),
        LiquibaseYamlChangelogWriter(),
        ModelDiff(),
        LiquibaseConstraintNaming(),
        SeedConflictChecker(YamlSeedDraftReader(), SeedFactory()),
    )


def run(args: argparse.Namespace, use_case: GenerateChangelogUseCaseInterface | None = None) -> int:
    """`0` — changelog записан, `1` — модель некорректна, неподдерживаема или конфликтует
    с принятым seed, `2` — окружение либо удаления в `auto` без согласия операции."""
    try:
        accepted = args.accepted or _accepted_model()
    except SettingsUnavailableError as error:
        return environment_error("accepted_root_invalid", str(error), operation=args.operation)
    seed = (
        getattr(args, "accepted_seed", None)
        or (PurePosixPath(accepted).parent / ACCEPTED_SEED).as_posix()
    )
    request = GenerateChangelogInput(args.model, accepted, args.operation, args.out, seed)
    try:
        output = (use_case or build_use_case()).execute(request)
    except OperationRecordUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=args.operation)
    except ModelUnreadableError as error:
        return environment_error("model_unreadable", str(error), model=error.path)
    except AcceptedModelError as error:
        return environment_error("accepted_model_invalid", str(error), accepted=accepted)
    except AcceptedSeedError as error:
        return environment_error("accepted_seed_invalid", str(error), accepted_seed=seed)
    except DropNotAllowedError as error:
        return environment_error(
            "drop_not_allowed",
            "удаления требуют согласия операции: беклог в режиме auto без allow_drop: true; "
            f"удаляемые объекты: {error}; продолжить с согласием — /forge --mode auto --allow-drop",
            objects=list(error.objects),
            operation=args.operation,
        )
    emit(_payload(output))
    return ExitCode.SUCCESS if output.generated else ExitCode.FAILURE


def _accepted_model() -> str:
    return (EnvironmentSettings(os.environ).accepted_root() / ACCEPTED_MODEL).as_posix()


def _payload(output: GenerateChangelogOutput) -> dict[str, Any]:
    return {
        "changelog": output.changelog_path,
        "logical_file_path": output.logical_file_path,
        "changesets": [
            {
                "id": c.id,
                "kind": c.kind,
                "table": c.table,
                "column": c.column,
                "constraint": c.constraint,
            }
            for c in output.changesets
        ],
        "violations": [
            {"path": v.path, "code": v.code, "message": v.message} for v in output.violations
        ],
        "non_additive": [
            {"code": c.code, "table": c.table, "column": c.column, "message": c.message}
            for c in output.non_additive
        ],
        "seed_conflict": [
            {
                "kind": c.kind,
                "table": c.table,
                "column": c.column,
                "path": c.path,
                "message": c.message,
            }
            for c in output.seed_conflict
        ],
    }
