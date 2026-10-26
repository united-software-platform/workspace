"""Входной контракт сценария закрытия операции."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloseOperationInput:
    """Беклог операции."""

    operation_path: str
