"""Выходной контракт сценария закрытия операции."""

from __future__ import annotations

from dataclasses import dataclass

from forge.operation.application.accepted_state import AcceptedFiles
from forge.operation.application.views import OperationView


@dataclass(frozen=True)
class CloseOperationOutput:
    """Операция после закрытия, принятая попытка и файлы `db/` при `success`."""

    operation: OperationView
    accepted_attempt: int | None
    accepted: AcceptedFiles | None
    changed: bool
