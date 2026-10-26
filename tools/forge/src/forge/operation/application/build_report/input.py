"""Входной контракт сценария отчёта."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuildReportInput:
    """Беклог операции."""

    operation_path: str
