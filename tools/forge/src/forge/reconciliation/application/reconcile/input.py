"""Входной контракт сценария сверки."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconcileInput:
    """Модель попытки и её changelog."""

    model_path: str
    changelog_path: str
