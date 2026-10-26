"""Выходной контракт сценария отказа от операции."""

from __future__ import annotations

from dataclasses import dataclass

from forge.operation.application.views import OperationView


@dataclass(frozen=True)
class AttemptRollbackView:
    """Откат начатой попытки: путь `rollback.json`, подтверждён ли и выполнен ли в этом вызове."""

    attempt: int
    result: str
    verified: bool
    performed: bool


@dataclass(frozen=True)
class AbandonOperationOutput:
    """Операция после отказа, откаты начатых попыток и был ли отказ сейчас."""

    operation: OperationView
    rollbacks: tuple[AttemptRollbackView, ...]
    changed: bool


class AbandonRefusedError(Exception):
    """Бросить операцию нельзя: она закрыта с `success`/`failure` либо откат не подтверждён.

    `rollbacks` — откаты, выполненные в этом вызове: их `rollback.json` остаются, повторный
    отказ их учтёт.
    """

    def __init__(self, reason: str, rollbacks: tuple[AttemptRollbackView, ...]) -> None:
        super().__init__(reason)
        self.rollbacks = rollbacks
