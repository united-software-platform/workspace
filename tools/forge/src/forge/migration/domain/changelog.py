"""Changelog операции: изменения схемы с назначенными `id` changeset."""

from __future__ import annotations

from dataclasses import dataclass

from forge.migration.domain.changes import SchemaChange
from forge.migration.domain.stamp import OperationStamp


@dataclass(frozen=True)
class ChangeSet:
    """Один changeset: одна таблица либо одна колонка."""

    id: str
    change: SchemaChange


@dataclass(frozen=True)
class Changelog:
    """Изменения в порядке исполнения; `id` назначаются по порядку от `<штамп>-01`."""

    stamp: OperationStamp
    changes: tuple[SchemaChange, ...]

    @property
    def logical_file_path(self) -> str:
        return self.stamp.logical_file_path

    @property
    def changesets(self) -> tuple[ChangeSet, ...]:
        return tuple(
            ChangeSet(self.stamp.changeset_id(number), change)
            for number, change in enumerate(self.changes, start=1)
        )
