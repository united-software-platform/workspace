"""Выходной контракт сценария наката."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplyChangelogOutput:
    """Исход наката и путь записанного `apply.json`."""

    result_path: str
    database: str
    request_id: str
    exit_code: int
    stdout: str
    stderr: str
    succeeded: bool
