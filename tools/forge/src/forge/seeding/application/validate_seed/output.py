"""Выходной контракт сценария проверки seed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ViolationView:
    """Нарушение seed в ответе: путь в файле seed, код из перечня формата, сообщение."""

    path: str
    code: str
    message: str


@dataclass(frozen=True)
class ValidateSeedOutput:
    """Итог проверки: пути seed и модели, признак корректности и все нарушения по порядку."""

    seed_path: str
    model_path: str
    valid: bool
    violations: tuple[ViolationView, ...]
