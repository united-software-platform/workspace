"""Входной контракт сценария проверки модели."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidateModelInput:
    """Путь файла модели в том виде, как его передал вызывающий."""

    model_path: str
