"""Проверка записи Liquibase о changeset попытки."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from forge.reconciliation.domain.discrepancy import Discrepancy

EXECUTED = "EXECUTED"


@dataclass(frozen=True)
class ExpectedChangeSet:
    """Changeset попытки: `id`, автор и файл, под которым Liquibase его записывает."""

    id: str
    author: str
    filename: str


@dataclass(frozen=True)
class JournalRecord:
    """Запись `DATABASECHANGELOG`."""

    id: str
    author: str
    filename: str
    exectype: str


class JournalCheck:
    """Доменный сервис: каждый changeset попытки записан с `EXECTYPE = EXECUTED`."""

    def compare(
        self, expected: Sequence[ExpectedChangeSet], records: Sequence[JournalRecord]
    ) -> tuple[Discrepancy, ...]:
        index = {(r.id, r.author, r.filename): r for r in records}
        discrepancies: list[Discrepancy] = []
        for changeset in expected:
            record = index.get((changeset.id, changeset.author, changeset.filename))
            actual = record.exectype if record is not None else "absent"
            if actual == EXECUTED:
                continue
            reason = "не записан в журнал" if record is None else f"записан с EXECTYPE {actual}"
            discrepancies.append(
                Discrepancy(
                    "changeset_not_executed",
                    None,
                    None,
                    changeset.id,
                    EXECUTED,
                    actual,
                    f"changeset {changeset.id} из {changeset.filename} {reason}",
                )
            )
        return tuple(discrepancies)
