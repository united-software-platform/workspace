"""Контракты Сверки: интроспекция схемы, журнал Liquibase, changeset попытки.

Реализации обращаются к БД и файловой системе, поэтому контракты объявлены в слое
приложения (CLAR-006).
"""

from __future__ import annotations

from typing import Protocol

from forge.reconciliation.domain.actual_schema import ActualSchema
from forge.reconciliation.domain.journal_check import ExpectedChangeSet, JournalRecord
from forge.shared.domain.target_database import TargetDatabase


class ChangelogUnreadableError(Exception):
    """Changelog попытки не прочитать или он не в формате `forge generate`."""


class SchemaIntrospectorInterface(Protocol):
    """Фактическая схема `public` без таблиц журнала Liquibase."""

    def read(self, database: TargetDatabase) -> ActualSchema: ...


class JournalRecordsReaderInterface(Protocol):
    """Записи `DATABASECHANGELOG`; таблицы журнала нет — записей нет."""

    def records(self, database: TargetDatabase) -> tuple[JournalRecord, ...]: ...


class ChangesetListReaderInterface(Protocol):
    """Changeset changelog попытки в порядке файла."""

    def read(self, path: str) -> tuple[ExpectedChangeSet, ...]:
        """Прочитать changelog; при ошибке — `ChangelogUnreadableError`."""
        ...
