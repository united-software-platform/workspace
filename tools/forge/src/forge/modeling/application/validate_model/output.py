"""Выходной контракт сценария проверки модели."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ViolationView:
    """Нарушение модели в ответе: путь в файле, код из перечня формата, сообщение."""

    path: str
    code: str
    message: str


@dataclass(frozen=True)
class ValidateModelOutput:
    """Итог проверки: путь модели, признак корректности и все нарушения по порядку."""

    model_path: str
    valid: bool
    violations: tuple[ViolationView, ...]
