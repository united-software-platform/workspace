"""Команда `forge generate-seed`: changelog данных из разницы seed."""

from __future__ import annotations

import argparse
import os
from typing import Any

from forge.cli.contract import ExitCode, emit, environment_error
from forge.migration.application.generate_changelog.use_case import (
    AcceptedModelError,
    DropNotAllowedError,
)
from forge.migration.application.operation_record import OperationRecordUnavailableError
from forge.migration.infrastructure.operation_record_reader import (
    FrontmatterOperationRecordReader,
)
from forge.modeling.application.load_model.use_case import LoadModelUseCase
from forge.modeling.application.model_reading import ModelUnreadableError
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.infrastructure.yaml_reader import YamlModelDraftReader
from forge.seeding.application.accepted_seed import AcceptedSeedError
from forge.seeding.application.generate_seed_changelog.input import GenerateSeedChangelogInput
from forge.seeding.application.generate_seed_changelog.output import GenerateSeedChangelogOutput
from forge.seeding.application.generate_seed_changelog.use_case import (
    GenerateSeedChangelogUseCase,
    GenerateSeedChangelogUseCaseInterface,
)
from forge.seeding.application.seed_reading import SeedUnreadableError
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.domain.seed_diff import SeedDiff
from forge.seeding.infrastructure.liquibase_data_changelog import (
    LiquibaseYamlDataChangelogWriter,
)
from forge.seeding.infrastructure.yaml_reader import YamlSeedDraftReader
from forge.shared.application.settings import SettingsUnavailableError
from forge.shared.infrastructure.settings import EnvironmentSettings

ACCEPTED_MODEL = "model.yaml"
ACCEPTED_SEED = "seed.yaml"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `generate-seed`."""
    parser = subparsers.add_parser("generate-seed", add_help=False)
    parser.add_argument("--seed", required=True)
    # Без `--accepted-seed` и `--model` они берутся из корня принятого состояния
    parser.add_argument("--accepted-seed")
    parser.add_argument("--model")
    parser.add_argument("--operation", required=True)
    parser.add_argument("--out", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> GenerateSeedChangelogUseCaseInterface:
    """Собрать сценарий с чтением беклога, моделью, разборщиком seed и записью YAML Liquibase."""
    return GenerateSeedChangelogUseCase(
        FrontmatterOperationRecordReader(),
        LoadModelUseCase(YamlModelDraftReader(), DataModelFactory()),
        YamlSeedDraftReader(),
        LiquibaseYamlDataChangelogWriter(),
        SeedFactory(),
        SeedDiff(),
    )


def run(
    args: argparse.Namespace, use_case: GenerateSeedChangelogUseCaseInterface | None = None
) -> int:
    """`0` — changelog записан, `1` — seed попытки нарушает формат или изменения неисполнимы,
    `2` — окружение, некорректные принятые модель или seed либо удаления без согласия."""
    operation: str = args.operation
    try:
        accepted_seed = args.accepted_seed or _accepted(ACCEPTED_SEED)
        model = args.model or _accepted(ACCEPTED_MODEL)
    except SettingsUnavailableError as error:
        return environment_error("accepted_root_invalid", str(error), operation=operation)
    request = GenerateSeedChangelogInput(
        args.seed,
        accepted_seed,
        model,
        operation,
        args.out,
        missing_model_as_empty=args.model is None,
    )
    try:
        output = (use_case or build_use_case()).execute(request)
    except OperationRecordUnavailableError as error:
        return environment_error("operation_unavailable", str(error), operation=operation)
    except SeedUnreadableError as error:
        return environment_error("seed_unreadable", str(error), seed=error.path)
    except ModelUnreadableError as error:
        return environment_error("model_unreadable", str(error), model=error.path)
    except AcceptedModelError as error:
        return environment_error("accepted_model_invalid", str(error), model=model)
    except AcceptedSeedError as error:
        return environment_error("accepted_seed_invalid", str(error), accepted_seed=accepted_seed)
    except DropNotAllowedError as error:
        return environment_error(
            "drop_not_allowed",
            "удаления строк требуют согласия операции: беклог в режиме auto без "
            f"allow_drop: true; удаляемые строки: {error}; продолжить с согласием — "
            "/forge --mode auto --allow-drop",
            objects=list(error.objects),
            operation=operation,
        )
    emit(_payload(output))
    return ExitCode.SUCCESS if output.generated else ExitCode.FAILURE


def _accepted(name: str) -> str:
    return (EnvironmentSettings(os.environ).accepted_root() / name).as_posix()


def _payload(output: GenerateSeedChangelogOutput) -> dict[str, Any]:
    return {
        "changelog": output.changelog_path,
        "logical_file_path": output.logical_file_path,
        "changesets": [
            {"id": c.id, "kind": c.kind, "table": c.table, "rows": c.rows}
            for c in output.changesets
        ],
        "deleted_rows": [{"table": d.table, "key": dict(d.key)} for d in output.deleted_rows],
        "violations": [
            {"path": v.path, "code": v.code, "message": v.message} for v in output.violations
        ],
        "unsupported": [
            {
                "code": c.code,
                "table": c.table,
                "columns": list(c.columns),
                "rows": list(c.rows),
                "message": c.message,
            }
            for c in output.unsupported
        ],
    }
