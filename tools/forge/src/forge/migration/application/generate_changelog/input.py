"""Входной контракт сценария построения changelog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateChangelogInput:
    """Модель попытки, принятая модель, беклог операции, путь changelog и принятый seed.

    `accepted_seed_path` — `None`: модель попытки с принятым seed не сверяется.
    """

    model_path: str
    accepted_path: str
    operation_path: str
    out_path: str
    accepted_seed_path: str | None = None
