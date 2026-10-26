"""Модели ответа команд операции."""

from __future__ import annotations

from dataclasses import dataclass

from forge.operation.domain.operation import Operation


@dataclass(frozen=True)
class AttemptView:
    """Попытка в ответе."""

    number: int
    verdict: str | None
    backlog: str | None
    directory: str


@dataclass(frozen=True)
class OperationView:
    """Операция в ответе: значения беклога и выводы агрегата."""

    path: str
    kind: str
    stamp: str
    intent: str
    mode: str
    allow_drop: bool
    status: str
    stop_reason: str | None
    attempts: tuple[AttemptView, ...]
    used_attempts: int
    confirmed_attempt: int | None


def operation_view(operation: Operation) -> OperationView:
    confirmed = operation.confirmed_attempt
    return OperationView(
        path=operation.path,
        kind=operation.kind.value,
        stamp=operation.stamp,
        intent=operation.intent,
        mode=operation.mode,
        allow_drop=operation.allow_drop,
        status=operation.status.value,
        stop_reason=operation.stop_reason,
        attempts=tuple(
            AttemptView(a.number, a.verdict, a.backlog, a.directory) for a in operation.attempts
        ),
        used_attempts=operation.used_attempts,
        confirmed_attempt=confirmed.number if confirmed else None,
    )
