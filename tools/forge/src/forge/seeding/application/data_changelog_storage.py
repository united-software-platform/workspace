"""Контракт записи файла changelog данных.

Контракт объявлен в слое приложения: его реализация обращается к файловой системе (CLAR-006).
"""

from __future__ import annotations

from typing import Protocol

from forge.seeding.domain.data_changelog import DataChangelog


class DataChangelogWriterInterface(Protocol):
    """Запись changelog данных в файл и удаление устаревшего файла."""

    def write(self, path: str, changelog: DataChangelog) -> None: ...

    def remove(self, path: str) -> None:
        """Удалить файл, если он есть."""
        ...
