"""Восстановление агрегата операции из модели чтения."""

from __future__ import annotations

from forge.operation.application.operation_reading import (
    OperationRecord,
    OperationUnavailableError,
)
from forge.operation.domain.factory import OperationFactory, OperationRestoreError
from forge.operation.domain.operation import ATTEMPT_LIMIT, Operation


def restore(record: OperationRecord, factory: OperationFactory) -> Operation:
    """Агрегат по записи беклога; значения вне домена — `OperationUnavailableError`."""
    try:
        return factory.restore(
            path=record.path,
            stamp=record.stamp,
            intent=record.intent,
            mode=record.mode,
            status=record.status,
            stop_reason=record.stop_reason,
            attempts=[
                (record.verdicts.get(n), record.backlogs.get(n), record.directories[n])
                for n in range(1, ATTEMPT_LIMIT + 1)
            ],
            allow_drop=record.allow_drop,
            kind=record.kind,
            seed_adjusted=record.seed_adjusted,
        )
    except OperationRestoreError as error:
        raise OperationUnavailableError(f"беклог операции {record.path}: {error}") from None
