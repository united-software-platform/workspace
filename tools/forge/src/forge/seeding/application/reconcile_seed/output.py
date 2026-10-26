"""Выходной контракт сценария сверки seed."""

from __future__ import annotations

from dataclasses import dataclass

from forge.reconciliation.domain.discrepancy import RowKey


@dataclass(frozen=True)
class SeedDiscrepancyView:
    """Расхождение в ответе; `key` — первичный ключ строки либо `None`."""

    kind: str
    table: str | None
    key: RowKey | None
    column: str | None
    changeset: str | None
    expected: str
    actual: str
    message: str


@dataclass(frozen=True)
class ReconcileSeedOutput:
    """Вердикт сверки seed, расхождения и путь `reconcile.json`."""

    result_path: str
    seed_path: str
    changelog_path: str
    database: str
    verdict: str
    discrepancies: tuple[SeedDiscrepancyView, ...]
