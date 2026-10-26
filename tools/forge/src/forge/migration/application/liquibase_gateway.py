"""Контракт шлюза Liquibase: накат и откат changelog на целевую БД."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forge.shared.domain.target_database import TargetDatabase


@dataclass(frozen=True)
class GatewayResult:
    """Исход Liquibase: код `0` — команда выполнена, `1` — Liquibase завершился ошибкой."""

    request_id: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0


class GatewayUnavailableError(Exception):
    """Liquibase не запускался: раннер недоступен, шлюз отказал или результат не прочитать."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class LiquibaseGatewayInterface(Protocol):
    """Накат и откат changelog через шлюз; путь changelog — относительно корня проекта."""

    def update(self, changelog: str, database: TargetDatabase) -> GatewayResult: ...

    def rollback(self, changelog: str, database: TargetDatabase, count: int) -> GatewayResult: ...
