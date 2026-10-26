"""Контракт отката попытки при отказе от операции."""

from __future__ import annotations

from typing import Protocol


class AttemptDiscarderInterface(Protocol):
    """Откат попытки при отказе: реализация уходит в контекст Миграции через точку сборки."""

    def discard(self, operation_path: str, attempt: int) -> bool:
        """Откатить попытку, в том числе с вердиктом `success`; `True` — возврат подтверждён.

        Итог пишется в `rollback.json` каталога попытки. Ошибки окружения — исключения
        контрактов отката, статус операции до них не меняется.
        """
        ...
