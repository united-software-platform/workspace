"""Сценарий отказа от открытой операции: откат начатых попыток и статус `abandoned`."""

from __future__ import annotations

from typing import Protocol

from forge.operation.application.abandon_operation.input import AbandonOperationInput
from forge.operation.application.abandon_operation.output import (
    AbandonOperationOutput,
    AbandonRefusedError,
    AttemptRollbackView,
)
from forge.operation.application.accepted_state import AttemptResultsReaderInterface
from forge.operation.application.attempt_discarder import AttemptDiscarderInterface
from forge.operation.application.operation_reading import OperationReadRepositoryInterface
from forge.operation.application.restore import restore
from forge.operation.application.views import operation_view
from forge.operation.domain.factory import OperationFactory
from forge.operation.domain.operation import OperationTransitionError
from forge.operation.domain.repository import OperationWriteRepositoryInterface

ROLLBACK_RESULT = "rollback.json"


class AbandonOperationUseCaseInterface(Protocol):
    """Бросить открытую операцию по решению владельца."""

    def execute(self, input: AbandonOperationInput) -> AbandonOperationOutput: ...


class AbandonOperationUseCase:
    """Откатывает начатые попытки без подтверждённого отката, исход решает агрегат.

    Попытки идут по убыванию номера: накатанной может быть только последняя начатая, прежние
    к этому моменту откатаны — так соблюдается правило хвоста журнала. Первый неподтверждённый
    откат останавливает обход: снимать записи ранней попытки поверх неснятой поздней нельзя.
    Закрытую операцию сценарий сразу отдаёт агрегату, ничего не откатывая. Ошибки окружения
    из отката прерывают сценарий до записи статуса.
    """

    def __init__(
        self,
        reads: OperationReadRepositoryInterface,
        writes: OperationWriteRepositoryInterface,
        results: AttemptResultsReaderInterface,
        discarder: AttemptDiscarderInterface,
        factory: OperationFactory,
    ) -> None:
        self._reads = reads
        self._writes = writes
        self._results = results
        self._discarder = discarder
        self._factory = factory

    def execute(self, input: AbandonOperationInput) -> AbandonOperationOutput:
        operation = restore(self._reads.get(input.operation_path), self._factory)
        views: list[AttemptRollbackView] = []
        rollbacks: dict[int, bool] = {}
        if not operation.status.closed:
            for attempt in sorted(operation.started_attempts, key=lambda a: -a.number):
                result = f"{attempt.directory}/{ROLLBACK_RESULT}"
                summary = self._results.rollback(attempt.directory)
                if summary is not None and summary.verified:
                    rollbacks[attempt.number] = True
                    views.append(AttemptRollbackView(attempt.number, result, True, False))
                    continue
                verified = self._discarder.discard(input.operation_path, attempt.number)
                rollbacks[attempt.number] = verified
                views.append(AttemptRollbackView(attempt.number, result, verified, True))
                if not verified:
                    break
        ordered = tuple(sorted(views, key=lambda view: view.attempt))
        try:
            outcome = operation.abandon(input.reason, rollbacks)
        except OperationTransitionError as error:
            raise AbandonRefusedError(
                str(error), tuple(view for view in ordered if view.performed)
            ) from None
        if outcome.changed:
            self._writes.save(operation)
        return AbandonOperationOutput(operation_view(operation), ordered, outcome.changed)
