"""Входной контракт сценария проверки seed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidateSeedInput:
    """Пути файлов seed и модели; `missing_model_as_empty` — нет файла модели, модель пуста."""

    seed_path: str
    model_path: str
    missing_model_as_empty: bool = False
