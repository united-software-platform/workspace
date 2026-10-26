"""Черновик seed: таблицы и строки с сырыми значениями, ещё не проверенные по модели.

Черновик — вход фабрики seed в терминах домена. Значение строки хранится сырым — вид скаляра
и его текст: тип колонки известен только по модели, поэтому приведение к типу делает домен,
а не тот, кто собрал черновик.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScalarKind(StrEnum):
    """Вид значения в файле seed, как его распознал разборщик."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    FLOAT = "float"
    NULL = "null"
    TIMESTAMP = "timestamp"
    OTHER = "other"
    """Список, отображение или скаляр с нестандартным тегом."""


_KIND_NAMES = {
    ScalarKind.STRING: "строка",
    ScalarKind.INTEGER: "целое число",
    ScalarKind.BOOLEAN: "логическое значение",
    ScalarKind.FLOAT: "дробное число",
    ScalarKind.NULL: "пустое значение",
    ScalarKind.TIMESTAMP: "дата",
}


@dataclass(frozen=True)
class RawValue:
    """Сырое значение колонки: вид и текст.

    Текст строки, даты и дробного числа — как записан в файле; текст целого и логического
    значения — каноническая запись (`10`, `true`); у значения вида `OTHER` текст описывает
    само значение (`список`).
    """

    kind: ScalarKind
    text: str

    def describe(self) -> str:
        """Вид и текст для сообщения: `строка '10'`, `список`."""
        name = _KIND_NAMES.get(self.kind)
        return self.text if name is None else f"{name} {self.text!r}"


@dataclass(frozen=True)
class RowDraft:
    """Строка как записана: пары «имя колонки → сырое значение» в порядке файла."""

    values: tuple[tuple[str, RawValue], ...]


@dataclass(frozen=True)
class SeedTableDraft:
    """Таблица seed как записана; `position` — её индекс в списке `tables` файла seed."""

    position: int
    name: str
    rows: tuple[RowDraft, ...]


@dataclass(frozen=True)
class SeedDraft:
    """Таблицы, прошедшие проверку структуры, в порядке файла seed.

    `excluded` — имена таблиц, записанных в файле, но исключённых из черновика из-за
    структурных нарушений: внешний ключ на такую таблицу не считается ссылкой вне seed,
    а ссылки на её строки не проверяются.
    """

    tables: tuple[SeedTableDraft, ...]
    excluded: tuple[str, ...] = ()
