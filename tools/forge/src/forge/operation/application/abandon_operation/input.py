"""Входной контракт сценария отказа от операции."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AbandonOperationInput:
    """Беклог операции и причина отказа."""

    operation_path: str
    reason: str
