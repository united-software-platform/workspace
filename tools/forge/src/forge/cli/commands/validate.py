"""Команда `forge validate --model <путь>`: проверка модели данных."""

from __future__ import annotations

import argparse
from typing import Any

from forge.cli.contract import ExitCode, emit, environment_error
from forge.modeling.application.model_reading import ModelUnreadableError
from forge.modeling.application.validate_model.input import ValidateModelInput
from forge.modeling.application.validate_model.output import ValidateModelOutput
from forge.modeling.application.validate_model.use_case import (
    ValidateModelUseCase,
    ValidateModelUseCaseInterface,
)
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.infrastructure.yaml_reader import YamlModelDraftReader


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `validate`."""
    parser = subparsers.add_parser("validate", add_help=False)
    parser.add_argument("--model", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> ValidateModelUseCaseInterface:
    """Собрать сценарий проверки с разборщиком YAML."""
    return ValidateModelUseCase(YamlModelDraftReader(), DataModelFactory())


def run(args: argparse.Namespace, use_case: ValidateModelUseCaseInterface | None = None) -> int:
    """Проверить модель: `0` — нарушений нет, `1` — есть, `2` — файл не прочитать."""
    model_path: str = args.model
    try:
        output = (use_case or build_use_case()).execute(ValidateModelInput(model_path))
    except ModelUnreadableError as error:
        return environment_error("model_unreadable", str(error), model=error.path)
    emit(_payload(output))
    return ExitCode.SUCCESS if output.valid else ExitCode.FAILURE


def _payload(output: ValidateModelOutput) -> dict[str, Any]:
    return {
        "model": output.model_path,
        "valid": output.valid,
        "violations": [
            {"path": v.path, "code": v.code, "message": v.message} for v in output.violations
        ],
    }
