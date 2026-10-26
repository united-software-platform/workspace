"""Входной контракт сценария наката."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplyChangelogInput:
    """Путь changelog относительно корня проекта."""

    changelog_path: str
