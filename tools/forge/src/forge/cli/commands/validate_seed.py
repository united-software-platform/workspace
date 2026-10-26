"""Команда `forge validate-seed --seed <путь> [--model <путь>]`: проверка seed по модели."""

from __future__ import annotations

import argparse
import os
from typing import Any

from forge.cli.contract import ExitCode, emit, environment_error
from forge.modeling.application.load_model.use_case import InvalidModelError, LoadModelUseCase
from forge.modeling.application.model_reading import ModelUnreadableError
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.infrastructure.yaml_reader import YamlModelDraftReader
from forge.seeding.application.seed_reading import SeedUnreadableError
from forge.seeding.application.validate_seed.input import ValidateSeedInput
from forge.seeding.application.validate_seed.output import ValidateSeedOutput
from forge.seeding.application.validate_seed.use_case import (
    ValidateSeedUseCase,
    ValidateSeedUseCaseInterface,
)
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.infrastructure.yaml_reader import YamlSeedDraftReader
from forge.shared.application.settings import SettingsUnavailableError
from forge.shared.infrastructure.settings import EnvironmentSettings

ACCEPTED_MODEL = "model.yaml"


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `validate-seed`."""
    parser = subparsers.add_parser("validate-seed", add_help=False)
    parser.add_argument("--seed", required=True)
    # Без `--model` seed проверяется по принятой модели корня принятого состояния
    parser.add_argument("--model")
    parser.set_defaults(handler=run)


def build_use_case() -> ValidateSeedUseCaseInterface:
    """Собрать сценарий с загрузкой модели и разборщиком seed в YAML."""
    return ValidateSeedUseCase(
        LoadModelUseCase(YamlModelDraftReader(), DataModelFactory()),
        YamlSeedDraftReader(),
        SeedFactory(),
    )


def run(args: argparse.Namespace, use_case: ValidateSeedUseCaseInterface | None = None) -> int:
    """`0` — нарушений нет, `1` — есть, `2` — seed или модель не прочитать, модель некорректна
    либо корень принятого состояния задан неверно."""
    seed_path: str = args.seed
    try:
        model_path = args.model or _accepted_model()
    except SettingsUnavailableError as error:
        return environment_error("accepted_root_invalid", str(error), seed=seed_path)
    request = ValidateSeedInput(seed_path, model_path, missing_model_as_empty=args.model is None)
    try:
        output = (use_case or build_use_case()).execute(request)
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
    emit(_payload(output))
    return ExitCode.SUCCESS if output.valid else ExitCode.FAILURE


def _accepted_model() -> str:
    return (EnvironmentSettings(os.environ).accepted_root() / ACCEPTED_MODEL).as_posix()


def _payload(output: ValidateSeedOutput) -> dict[str, Any]:
    return {
        "seed": output.seed_path,
        "model": output.model_path,
        "valid": output.valid,
        "violations": [
            {"path": v.path, "code": v.code, "message": v.message} for v in output.violations
        ],
    }
