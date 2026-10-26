"""Операция Liquibase Forge — корень агрегата контекста Операция."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

ATTEMPT_LIMIT = 3
AUTO = "auto"
SUCCESS = "success"
FAILURE = "failure"


class OperationKind(StrEnum):
    """Вид операции: `model` строит модель данных, `seed` наполняет справочные таблицы."""

    MODEL = "model"
    SEED = "seed"


class OperationStatus(StrEnum):
    """Статус операции: открыта (`running`, `stopped`) либо закрыта (`success`, `failure`,
    `abandoned` — брошена владельцем, ничего не принято)."""

    RUNNING = "running"
    STOPPED = "stopped"
    SUCCESS = "success"
    FAILURE = "failure"
    ABANDONED = "abandoned"

    @property
    def closed(self) -> bool:
        return self in (OperationStatus.SUCCESS, OperationStatus.FAILURE, OperationStatus.ABANDONED)


class OperationTransitionError(Exception):
    """Переход статуса недопустим: операция не меняется."""


class OperationClosedError(OperationTransitionError):
    """Операция уже закрыта."""


class OperationNotStoppedError(OperationTransitionError):
    """Продолжить можно только остановленную операцию."""


class OperationDropConsentError(OperationTransitionError):
    """Согласие на удаления даётся только операции в режиме `auto`."""


class OperationNotClosableError(OperationTransitionError):
    """Закрывать операцию рано: нет ни подтверждённой попытки, ни трёх неудач с откатом."""


class OperationNotAbandonableError(OperationTransitionError):
    """Бросить операцию нельзя: откат начатой попытки не подтверждён."""

    def __init__(self, attempts: tuple[int, ...]) -> None:
        super().__init__(f"откат не подтверждён у попыток {', '.join(map(str, attempts))}")
        self.attempts = attempts


@dataclass(frozen=True)
class Attempt:
    """Попытка: номер, вердикт сверки, беклог попытки и каталог её артефактов."""

    number: int
    verdict: str | None
    backlog: str | None
    directory: str

    @property
    def used(self) -> bool:
        return self.verdict is not None

    @property
    def started(self) -> bool:
        """Попытка начата: её беклог порождён, накат мог состояться и без вердикта."""
        return self.backlog is not None


@dataclass(frozen=True)
class CloseOutcome:
    """Исход закрытия: статус, принятая попытка при `success` и было ли закрытие сейчас."""

    status: OperationStatus
    accepted_attempt: int | None
    changed: bool


@dataclass(frozen=True)
class AbandonOutcome:
    """Исход отказа: статус и был ли отказ сейчас."""

    status: OperationStatus
    changed: bool


class Operation:
    """Операция: вид, намерение, режим, согласие на удаления, статус, причина остановки и попытки.

    Статус меняют только операции агрегата: `stop`, `resume`, `close`, `abandon`. Вердикты попыток
    записывает исполнение беклога, агрегат их только читает. Согласие `allow_drop` задаётся
    при начале операции либо даётся остановленной операции в режиме `auto` и не снимается.
    `seed_adjusted` — закрытие операции модели убрало удалённые колонки из принятого seed.
    """

    def __init__(
        self,
        path: str,
        stamp: str,
        intent: str,
        mode: str,
        status: OperationStatus,
        stop_reason: str | None,
        attempts: tuple[Attempt, ...],
        allow_drop: bool = False,
        kind: OperationKind = OperationKind.MODEL,
        seed_adjusted: bool = False,
    ) -> None:
        self.path = path
        self.kind = kind
        self.seed_adjusted = seed_adjusted
        self.stamp = stamp
        self.intent = intent
        self.mode = mode
        self.allow_drop = allow_drop
        self._status = status
        self._stop_reason = stop_reason
        self.attempts = attempts

    @property
    def status(self) -> OperationStatus:
        return self._status

    @property
    def stop_reason(self) -> str | None:
        return self._stop_reason

    @property
    def confirmed_attempt(self) -> Attempt | None:
        """Первая попытка с вердиктом `success`."""
        return next((a for a in self.attempts if a.verdict == SUCCESS), None)

    @property
    def used_attempts(self) -> int:
        return sum(1 for attempt in self.attempts if attempt.used)

    @property
    def started_attempts(self) -> tuple[Attempt, ...]:
        return tuple(attempt for attempt in self.attempts if attempt.started)

    def attempt(self, number: int) -> Attempt:
        return next(a for a in self.attempts if a.number == number)

    def stop(self, reason: str) -> None:
        """Остановить открытую операцию; повторная остановка заменяет причину."""
        if self._status.closed:
            raise OperationClosedError(f"операция закрыта со статусом {self._status}")
        self._status = OperationStatus.STOPPED
        self._stop_reason = reason

    def grant_drop(self) -> None:
        """Дать согласие на удаления остановленной операции в `auto`; повтор ничего не меняет."""
        if self._status.closed:
            raise OperationClosedError(f"операция закрыта со статусом {self._status}")
        if self._status is not OperationStatus.STOPPED:
            raise OperationNotStoppedError(
                f"согласие даётся только остановленной операции: статус {self._status}"
            )
        if self.mode != AUTO:
            raise OperationDropConsentError(
                f"согласие на удаления действует только в режиме auto, режим операции {self.mode}"
            )
        self.allow_drop = True

    def resume(self) -> None:
        """Продолжить остановленную операцию."""
        if self._status.closed:
            raise OperationClosedError(f"операция закрыта со статусом {self._status}")
        if self._status is not OperationStatus.STOPPED:
            raise OperationNotStoppedError(f"операция не остановлена: статус {self._status}")
        self._status = OperationStatus.RUNNING
        self._stop_reason = None

    def close(self, rollbacks: Mapping[int, bool]) -> CloseOutcome:
        """Закрыть операцию по вердиктам попыток и подтверждению откатов.

        `rollbacks` — подтверждён ли откат попытки по её `rollback.json`. Повторное закрытие
        закрытой операции ничего не меняет и сообщает прежний исход.
        """
        confirmed = self.confirmed_attempt
        if self._status.closed:
            number = (
                confirmed.number if self._status is OperationStatus.SUCCESS and confirmed else None
            )
            return CloseOutcome(self._status, number, changed=False)
        if self._status is OperationStatus.STOPPED:
            raise OperationNotClosableError("операция остановлена: сначала forge resume")
        if confirmed is not None:
            self._status = OperationStatus.SUCCESS
            return CloseOutcome(self._status, confirmed.number, changed=True)
        failed = [a for a in self.attempts if a.verdict == FAILURE]
        unconfirmed = [a.number for a in failed if not rollbacks.get(a.number, False)]
        if len(failed) == ATTEMPT_LIMIT and not unconfirmed:
            self._status = OperationStatus.FAILURE
            return CloseOutcome(self._status, None, changed=True)
        reason = (
            f"откат не подтверждён у попыток {', '.join(map(str, unconfirmed))}"
            if unconfirmed
            else f"подтверждённой попытки нет, неуспешных попыток {len(failed)} из {ATTEMPT_LIMIT}"
        )
        raise OperationNotClosableError(f"закрывать рано: {reason}")

    def adjust_seed(self) -> None:
        """Отметить, что закрытие с `success` согласовало принятый seed с принятой моделью."""
        if self.kind is not OperationKind.MODEL or self._status is not OperationStatus.SUCCESS:
            raise OperationTransitionError(
                "принятый seed согласует только закрытие операции модели с success"
            )
        self.seed_adjusted = True

    def abandon(self, reason: str, rollbacks: Mapping[int, bool]) -> AbandonOutcome:
        """Бросить открытую операцию по решению владельца; причина пишется в `stop_reason`.

        `rollbacks` — подтверждён ли откат начатой попытки. Откатывает не агрегат: он только
        проверяет, что схема возвращена по каждой начатой попытке. Повторный отказ от брошенной
        операции ничего не меняет; операцию, закрытую с `success` или `failure`, бросить нельзя.
        """
        if self._status is OperationStatus.ABANDONED:
            return AbandonOutcome(self._status, changed=False)
        if self._status.closed:
            raise OperationClosedError(f"операция закрыта со статусом {self._status}")
        unconfirmed = tuple(
            a.number for a in self.started_attempts if not rollbacks.get(a.number, False)
        )
        if unconfirmed:
            raise OperationNotAbandonableError(unconfirmed)
        self._status = OperationStatus.ABANDONED
        self._stop_reason = reason
        return AbandonOutcome(self._status, changed=True)
