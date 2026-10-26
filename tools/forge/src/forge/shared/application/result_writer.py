"""Контракт записи файла результата команды: `apply.json`, `rollback.json`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ResultWriterInterface(Protocol):
    """Записать документ результата целиком по пути."""

    def write(self, path: str, document: Mapping[str, Any]) -> None: ...
