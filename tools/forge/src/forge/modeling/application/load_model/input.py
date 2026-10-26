"""Входной контракт сценария загрузки модели."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadModelInput:
    """Путь файла модели; `missing_as_empty` — отсутствующий файл означает пустую модель."""

    model_path: str
    missing_as_empty: bool = False
