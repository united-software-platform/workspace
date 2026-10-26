"""Сценарий наката changelog на целевую БД через шлюз Liquibase."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol

from forge.migration.application.apply_changelog.input import ApplyChangelogInput
from forge.migration.application.apply_changelog.output import ApplyChangelogOutput
from forge.migration.application.liquibase_gateway import LiquibaseGatewayInterface
from forge.shared.application.result_writer import ResultWriterInterface
from forge.shared.application.settings import TargetDatabaseSettingsInterface

APPLY_RESULT = "apply.json"


class ApplyChangelogUseCaseInterface(Protocol):
    """Накатить changelog на целевую БД."""

    def execute(self, input: ApplyChangelogInput) -> ApplyChangelogOutput: ...


class ApplyChangelogUseCase:
    """Проверка перечня тестовых до раннера, накат, `apply.json` рядом с changelog.

    `apply.json` пишется только при исходе Liquibase — успехе или ошибке. Ошибки окружения
    (`SettingsUnavailableError`, `DatabaseNotAllowedError`, `GatewayUnavailableError`) файла
    не оставляют: иначе беклог счёл бы накат выполненным.
    """

    def __init__(
        self,
        settings: TargetDatabaseSettingsInterface,
        gateway: LiquibaseGatewayInterface,
        writer: ResultWriterInterface,
    ) -> None:
        self._settings = settings
        self._gateway = gateway
        self._writer = writer

    def execute(self, input: ApplyChangelogInput) -> ApplyChangelogOutput:
        target = self._settings.target()
        self._settings.allowlist().require(target)
        result = self._gateway.update(input.changelog_path, target)
        result_path = str(PurePosixPath(input.changelog_path).parent / APPLY_RESULT)
        self._writer.write(
            result_path,
            {
                "changelog": input.changelog_path,
                "database": {"host": target.host, "port": target.port, "name": target.name},
                "request_id": result.request_id,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
        return ApplyChangelogOutput(
            result_path=result_path,
            database=str(target),
            request_id=result.request_id,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            succeeded=result.succeeded,
        )
