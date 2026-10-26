"""Сценарий статуса операции и проверки тестовой среды."""

from __future__ import annotations

from typing import Protocol

from forge.operation.application.environment import EnvironmentProbeInterface
from forge.operation.application.get_status.input import GetStatusInput
from forge.operation.application.get_status.output import GetStatusOutput
from forge.operation.application.operation_reading import (
    OperationReadRepositoryInterface,
    SeveralOpenOperationsError,
)
from forge.operation.application.restore import restore
from forge.operation.application.views import OperationView, operation_view
from forge.operation.domain.factory import OperationFactory


class GetStatusUseCaseInterface(Protocol):
    """Статус операции и среды."""

    def execute(self, input: GetStatusInput) -> GetStatusOutput: ...


class GetStatusUseCase:
    """Операция по пути либо единственная открытая операция следа и проверки среды.

    Больше одной открытой операции — `SeveralOpenOperationsError`; нечитаемый беклог по пути —
    `OperationUnavailableError` контракта чтения.
    """

    def __init__(
        self,
        reads: OperationReadRepositoryInterface,
        probe: EnvironmentProbeInterface,
        factory: OperationFactory,
    ) -> None:
        self._reads = reads
        self._probe = probe
        self._factory = factory

    def execute(self, input: GetStatusInput) -> GetStatusOutput:
        path = input.operation_path or self._latest_open()
        view: OperationView | None = None
        if path is not None:
            view = operation_view(restore(self._reads.get(path), self._factory))
        checks = self._probe.check()
        return GetStatusOutput(view, checks, all(check.passed for check in checks))

    def _latest_open(self) -> str | None:
        found = self._reads.open_operations()
        if len(found) > 1:
            raise SeveralOpenOperationsError(found)
        return found[0] if found else None
