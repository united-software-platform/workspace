"""Выходной контракт сценария сверки."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscrepancyView:
    """Расхождение в ответе."""

    kind: str
    table: str | None
    column: str | None
    changeset: str | None
    expected: str
    actual: str
    message: str


@dataclass(frozen=True)
class ReconcileOutput:
    """Вердикт сверки, расхождения и путь `reconcile.json`."""

    result_path: str
    model_path: str
    changelog_path: str
    database: str
    verdict: str
    discrepancies: tuple[DiscrepancyView, ...]
