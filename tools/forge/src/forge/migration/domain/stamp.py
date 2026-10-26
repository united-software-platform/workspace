"""Штамп операции: UTC-время её начала в виде `YYYYMMDD-HHMMSS`."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERN = re.compile(r"\d{8}-\d{6}")


class InvalidStampError(ValueError):
    """Значение не соответствует шаблону штампа `YYYYMMDD-HHMMSS`."""


@dataclass(frozen=True)
class OperationStamp:
    """Штамп операции: из него строятся путь принятого changelog и `id` changeset."""

    value: str

    def __post_init__(self) -> None:
        if not _PATTERN.fullmatch(self.value):
            raise InvalidStampError(
                f"штамп операции {self.value!r} не соответствует шаблону YYYYMMDD-HHMMSS"
            )

    @property
    def logical_file_path(self) -> str:
        """Путь, под которым changelog операции будет принят в `db/`."""
        return f"db/changelog/{self.value}.yaml"

    def changeset_id(self, number: int) -> str:
        """`id` changeset с порядковым номером от 1: `<штамп>-01`, …, `<штамп>-100`."""
        if number < 1:
            raise ValueError(f"номер changeset начинается с 1, получено {number}")
        return f"{self.value}-{number:02d}"

    def __str__(self) -> str:
        return self.value
