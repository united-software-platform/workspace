"""Сценарии остановки и продолжения операции."""

from __future__ import annotations

from typing import Protocol

from forge.operation.application.change_status.input import (
    ResumeOperationInput,
    StopOperationInput,
)
from forge.operation.application.operation_reading import OperationReadRepositoryInterface
from forge.operation.application.restore import restore
from forge.operation.application.views import OperationView, operation_view
from forge.operation.domain.factory import OperationFactory
from forge.operation.domain.repository import OperationWriteRepositoryInterface


class StopOperationUseCaseInterface(Protocol):
    """Остановить операцию с причиной."""

    def execute(self, input: StopOperationInput) -> OperationView: ...


class ResumeOperationUseCaseInterface(Protocol):
    """Продолжить остановленную операцию."""

    def execute(self, input: ResumeOperationInput) -> OperationView: ...


class StopOperationUseCase:
    """Читает операцию, останавливает агрегат, сохраняет статус и причину.

    Недопустимый переход — `OperationTransitionError` агрегата, беклог не меняется.
    """

    def __init__(
        self,
        reads: OperationReadRepositoryInterface,
        writes: OperationWriteRepositoryInterface,
        factory: OperationFactory,
    ) -> None:
        self._reads = reads
        self._writes = writes
        self._factory = factory

    def execute(self, input: StopOperationInput) -> OperationView:
        operation = restore(self._reads.get(input.operation_path), self._factory)
        operation.stop(input.reason)
        self._writes.save(operation)
        return operation_view(operation)


class ResumeOperationUseCase:
    """Читает операцию, возвращает агрегат в `running`, сохраняет статус.

    С `allow_drop` сначала даёт агрегату согласие на удаления и записывает его, затем статус:
    недопустимое согласие — `OperationTransitionError`, беклог не меняется; повтор безопасен.
    """

    def __init__(
        self,
        reads: OperationReadRepositoryInterface,
        writes: OperationWriteRepositoryInterface,
        factory: OperationFactory,
    ) -> None:
        self._reads = reads
        self._writes = writes
        self._factory = factory

    def execute(self, input: ResumeOperationInput) -> OperationView:
        operation = restore(self._reads.get(input.operation_path), self._factory)
        if input.allow_drop:
            operation.grant_drop()
        operation.resume()
        if input.allow_drop:
            self._writes.save_drop_consent(operation)
        self._writes.save(operation)
        return operation_view(operation)
