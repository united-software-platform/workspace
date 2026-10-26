"""Входной контракт сценария сверки seed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconcileSeedInput:
    """Seed попытки, её changelog данных, принятый seed и модель.

    Нет файла принятого seed — принятый seed пуст. `missing_model_as_empty` — нет файла
    модели, модель пуста: так ведёт себя принятая модель до первой операции.
    """

    seed_path: str
    changelog_path: str
    accepted_seed_path: str
    model_path: str
    missing_model_as_empty: bool = False
