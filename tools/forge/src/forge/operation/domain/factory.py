"""Фабрика операции: восстанавливает агрегат из значений беклога операции."""

from __future__ import annotations

import re
from collections.abc import Sequence

from forge.operation.domain.operation import (
    ATTEMPT_LIMIT,
    FAILURE,
    SUCCESS,
    Attempt,
    Operation,
    OperationKind,
    OperationStatus,
)

MODES = ("interactive", "auto")
_STAMP = re.compile(r"\d{8}-\d{6}")


class OperationRestoreError(ValueError):
    """Значения беклога не описывают операцию: неизвестный вид, статус, режим, вердикт или штамп."""


class OperationFactory:
    """Проверяет значения беклога и строит из них агрегат (DDD-023)."""

    def restore(
        self,
        path: str,
        stamp: str,
        intent: str,
        mode: str,
        status: str,
        stop_reason: str | None,
        attempts: Sequence[tuple[str | None, str | None, str]],
        allow_drop: bool = False,
        kind: str = OperationKind.MODEL.value,
        seed_adjusted: bool = False,
    ) -> Operation:
        """`attempts` — по попытке 1..3: вердикт, путь беклога попытки, каталог попытки."""
        if not _STAMP.fullmatch(stamp):
            raise OperationRestoreError(f"штамп операции {stamp!r} не в виде YYYYMMDD-HHMMSS")
        try:
            operation_kind = OperationKind(kind)
        except ValueError:
            raise OperationRestoreError(f"неизвестный вид операции {kind!r}") from None
        if mode not in MODES:
            raise OperationRestoreError(f"режим операции {mode!r} не interactive и не auto")
        try:
            operation_status = OperationStatus(status)
        except ValueError:
            raise OperationRestoreError(f"неизвестный статус операции {status!r}") from None
        if len(attempts) != ATTEMPT_LIMIT:
            raise OperationRestoreError(f"попыток должно быть {ATTEMPT_LIMIT}")
        restored: list[Attempt] = []
        for number, (verdict, backlog, directory) in enumerate(attempts, start=1):
            if verdict not in (SUCCESS, FAILURE, None):
                raise OperationRestoreError(
                    f"вердикт попытки {number} должен быть success, failure или null: {verdict!r}"
                )
            restored.append(Attempt(number, verdict, backlog, directory))
        return Operation(
            path,
            stamp,
            intent,
            mode,
            operation_status,
            stop_reason,
            tuple(restored),
            allow_drop=allow_drop,
            kind=operation_kind,
            seed_adjusted=seed_adjusted,
        )
