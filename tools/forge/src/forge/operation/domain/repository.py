"""Контракт записи операции (CQRS-001): только изменение состояния."""

from __future__ import annotations

from typing import Protocol

from forge.operation.domain.operation import Operation


class OperationWriteRepositoryInterface(Protocol):
    """Сохранить статус и причину остановки операции в её беклоге и согласие на удаления."""

    def save(self, operation: Operation) -> None:
        """Записать статус и причину остановки; остальной текст беклога не меняется."""
        ...

    def save_drop_consent(self, operation: Operation) -> None:
        """Записать `allow_drop: true` в беклог операции и в беклоги её попыток."""
        ...
