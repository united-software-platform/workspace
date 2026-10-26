"""Команда `forge apply --changelog <путь>`: накат changelog на целевую БД."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from forge.cli.contract import ExitCode, emit, environment_error
from forge.migration.application.apply_changelog.input import ApplyChangelogInput
from forge.migration.application.apply_changelog.use_case import (
    ApplyChangelogUseCase,
    ApplyChangelogUseCaseInterface,
)
from forge.migration.application.liquibase_gateway import GatewayUnavailableError
from forge.migration.infrastructure.runner_gateway import RunnerLiquibaseGateway
from forge.shared.application.settings import SettingsUnavailableError
from forge.shared.domain.target_database import DatabaseNotAllowedError
from forge.shared.infrastructure.json_result_writer import JsonResultWriter
from forge.shared.infrastructure.runner import runner_settings
from forge.shared.infrastructure.settings import EnvironmentSettings


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Добавить подкоманду `apply`."""
    parser = subparsers.add_parser("apply", add_help=False)
    parser.add_argument("--changelog", required=True)
    parser.set_defaults(handler=run)


def build_use_case() -> ApplyChangelogUseCaseInterface:
    """Собрать сценарий: настройки из окружения, шлюз через раннер, корень — текущий каталог."""
    settings = EnvironmentSettings(os.environ)
    gateway = RunnerLiquibaseGateway(Path.cwd(), runner_settings(os.environ))
    return ApplyChangelogUseCase(settings, gateway, JsonResultWriter())


def run(args: argparse.Namespace, use_case: ApplyChangelogUseCaseInterface | None = None) -> int:
    """`0` — накат выполнен, `1` — ошибка Liquibase, `2` — БД вне перечня или окружение."""
    changelog: str = args.changelog
    try:
        output = (use_case or build_use_case()).execute(ApplyChangelogInput(changelog))
    except SettingsUnavailableError as error:
        return environment_error("settings_unavailable", str(error))
    except DatabaseNotAllowedError as error:
        return environment_error("database_not_allowed", str(error))
    except GatewayUnavailableError as error:
        return environment_error(error.kind, str(error), changelog=changelog)
    if not output.succeeded and output.stderr:
        sys.stderr.write(output.stderr if output.stderr.endswith("\n") else output.stderr + "\n")
    emit(
        {
            "changelog": changelog,
            "result": output.result_path,
            "database": output.database,
            "request_id": output.request_id,
            "exit_code": output.exit_code,
        }
    )
    return ExitCode.SUCCESS if output.succeeded else ExitCode.FAILURE
