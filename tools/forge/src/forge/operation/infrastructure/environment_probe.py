"""Проверка тестовой среды: целевая БД, перечень тестовых БД, раннер, корень принятого состояния."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping

from forge.operation.application.environment import EnvironmentCheck
from forge.shared.application.settings import (
    DatabaseCredentials,
    DatabaseUnavailableError,
    RunnerUnavailableError,
    SettingsUnavailableError,
)
from forge.shared.domain.target_database import DatabaseNotAllowedError
from forge.shared.infrastructure.postgres import PostgresConnector
from forge.shared.infrastructure.runner import RunnerCall, call_runner, runner_settings
from forge.shared.infrastructure.settings import EnvironmentSettings

# Цель раннера без побочных эффектов: проверяет, что раннер жив и принимает токен
RUNNER_PROBE_TARGET = "help"
RUNNER_PROBE_TIMEOUT = 30.0


class EnvironmentProbe:
    """Реализация проверки среды по переменным окружения процесса."""

    def __init__(
        self,
        environment: Mapping[str, str],
        connector: Callable[[DatabaseCredentials], PostgresConnector] = PostgresConnector,
        call: RunnerCall = call_runner,
    ) -> None:
        self._env = environment
        self._settings = EnvironmentSettings(environment)
        self._connector = connector
        self._call = call

    def check(self) -> tuple[EnvironmentCheck, ...]:
        return (self._database(), self._allowlist(), self._runner(), self._accepted())

    def _database(self) -> EnvironmentCheck:
        try:
            target = self._settings.target()
            connector = self._connector(self._settings.credentials())
            with connector.connect(target) as connection:
                connection.execute("SELECT 1")
        except (SettingsUnavailableError, DatabaseUnavailableError) as error:
            return EnvironmentCheck("database", False, str(error))
        return EnvironmentCheck("database", True, f"подключение к {target} выполнено")

    def _allowlist(self) -> EnvironmentCheck:
        try:
            target = self._settings.target()
            self._settings.allowlist().require(target)
        except (SettingsUnavailableError, DatabaseNotAllowedError) as error:
            return EnvironmentCheck("allowlist", False, str(error))
        return EnvironmentCheck("allowlist", True, f"{target} входит в перечень тестовых")

    def _runner(self) -> EnvironmentCheck:
        try:
            settings = runner_settings(self._env)
            if settings is None:
                return EnvironmentCheck(
                    "runner",
                    False,
                    "раннер не настроен: не заданы AGENT_RUNNER_URL и AGENT_RUNNER_TOKEN",
                )
            probe = dataclasses.replace(
                settings, timeout=min(settings.timeout, RUNNER_PROBE_TIMEOUT)
            )
            self._call(probe, RUNNER_PROBE_TARGET)
        except (SettingsUnavailableError, RunnerUnavailableError) as error:
            return EnvironmentCheck("runner", False, str(error))
        return EnvironmentCheck("runner", True, f"раннер {settings.url} отвечает")

    def _accepted(self) -> EnvironmentCheck:
        # Существование каталога не проверяется: до первого `forge close` корня нет
        try:
            root = self._settings.accepted_root()
        except SettingsUnavailableError as error:
            return EnvironmentCheck("accepted", False, str(error))
        return EnvironmentCheck("accepted", True, f"корень принятого состояния {root.as_posix()}")
