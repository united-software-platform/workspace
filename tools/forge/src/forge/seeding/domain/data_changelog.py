"""Changelog данных операции: группы изменений строк с назначенными `id` changeset."""

from __future__ import annotations

from dataclasses import dataclass

from forge.migration.domain.stamp import OperationStamp
from forge.seeding.domain.row_changes import RowDelete, RowGroup


@dataclass(frozen=True)
class DataChangeSet:
    """Один changeset данных: изменения строк одной таблицы и одного вида."""

    id: str
    group: RowGroup


@dataclass(frozen=True)
class DataChangelog:
    """Группы в порядке исполнения; `id` назначаются, как у changelog модели, от `<штамп>-01`."""

    stamp: OperationStamp
    groups: tuple[RowGroup, ...]

    @property
    def logical_file_path(self) -> str:
        return self.stamp.logical_file_path

    @property
    def changesets(self) -> tuple[DataChangeSet, ...]:
        return tuple(
            DataChangeSet(self.stamp.changeset_id(number), group)
            for number, group in enumerate(self.groups, start=1)
        )

    def deleted_rows(self) -> tuple[RowDelete, ...]:
        """Удаляемые строки в порядке исполнения."""
        return tuple(
            change
            for group in self.groups
            for change in group.changes
            if isinstance(change, RowDelete)
        )
