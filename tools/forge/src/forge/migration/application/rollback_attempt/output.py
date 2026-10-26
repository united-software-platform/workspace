"""Выходной контракт сценария отката попытки."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckView:
    """Одна проверка возврата: что проверено, пройдена ли, подробности."""

    check: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class RollbackAttemptOutput:
    """Итог отката: путь `rollback.json` (нет при вердикте `success`), действие и проверка."""

    result_path: str | None
    attempt: int
    verdict: str | None
    action: str
    rolled_back: int
    fallback_reason: str | None
    checks: tuple[CheckView, ...]
    verified: bool
