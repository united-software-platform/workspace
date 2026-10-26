"""Общее для команд операции: сборка хранилища беклогов и ответ об операции."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from forge.operation.application.views import OperationView
from forge.operation.infrastructure.accepted_state import FileAcceptedState
from forge.operation.infrastructure.frontmatter import (
    FrontmatterOperationReadRepository,
    FrontmatterOperationWriteRepository,
)
from forge.shared.infrastructure.settings import EnvironmentSettings


def trail_root() -> Path:
    """Корень следа: `BACKLOG_ROOT` либо `backlog` в текущем каталоге, как у плагина `formular`."""
    return Path(os.environ.get("BACKLOG_ROOT") or "backlog")


def read_repository() -> FrontmatterOperationReadRepository:
    return FrontmatterOperationReadRepository(trail_root())


def write_repository() -> FrontmatterOperationWriteRepository:
    return FrontmatterOperationWriteRepository()


def accepted_state() -> FileAcceptedState:
    """Принятое состояние в корне `FORGE_ACCEPTED_DIR`; некорректный корень — ошибка настроек."""
    return FileAcceptedState(EnvironmentSettings(os.environ).accepted_root())


def operation_payload(view: OperationView) -> dict[str, Any]:
    """Операция в ответе команды."""
    return {
        "path": view.path,
        "kind": view.kind,
        "stamp": view.stamp,
        "intent": view.intent,
        "mode": view.mode,
        "allow_drop": view.allow_drop,
        "status": view.status,
        "stop_reason": view.stop_reason,
        "used_attempts": view.used_attempts,
        "confirmed_attempt": view.confirmed_attempt,
        "attempts": [
            {
                "number": a.number,
                "verdict": a.verdict,
                "backlog": a.backlog,
                "directory": a.directory,
            }
            for a in view.attempts
        ],
    }
