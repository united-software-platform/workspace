"""Контракт настроек целевой БД: адрес, учётные данные, перечень тестовых БД и ошибки доступа."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge.shared.domain.target_database import TargetDatabase, TestDatabaseAllowlist


class SettingsUnavailableError(Exception):
    """Настройки окружения не заданы или заданы неверно."""


class DatabaseUnavailableError(Exception):
    """К целевой БД или серверу не подключиться либо запрос не выполнен."""


class RunnerUnavailableError(Exception):
    """Раннер на хосте не отвечает или отклонил цель."""


@dataclass(frozen=True)
class DatabaseCredentials:
    """Учётные данные целевой БД для прямого подключения."""

    user: str
    password: str


class TargetDatabaseSettingsInterface(Protocol):
    """Целевая БД операций и перечень тестовых БД."""

    def target(self) -> TargetDatabase: ...

    def credentials(self) -> DatabaseCredentials: ...

    def allowlist(self) -> TestDatabaseAllowlist: ...
