"""Входной контракт сценария построения changelog данных."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateSeedChangelogInput:
    """Seed попытки, принятый seed, модель, беклог операции и путь changelog.

    Нет файла принятого seed — принятый seed пуст. `missing_model_as_empty` — нет файла
    модели, модель пуста: так ведёт себя принятая модель до первой операции.
    """

    seed_path: str
    accepted_seed_path: str
    model_path: str
    operation_path: str
    out_path: str
    missing_model_as_empty: bool = False
