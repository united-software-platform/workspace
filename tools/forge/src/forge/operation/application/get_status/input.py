"""Входной контракт сценария статуса."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetStatusInput:
    """Беклог операции либо `None` — найти открытую операцию в следе."""

    operation_path: str | None
