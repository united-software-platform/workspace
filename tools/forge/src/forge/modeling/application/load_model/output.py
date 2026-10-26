"""Выходной контракт сценария загрузки модели."""

from __future__ import annotations

from dataclasses import dataclass

from forge.modeling.domain.data_model import DataModel


@dataclass(frozen=True)
class LoadModelOutput:
    """Загруженная модель; `found` — ложь, если файла не было и модель пустая."""

    model: DataModel
    found: bool
