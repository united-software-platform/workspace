"""Имена таблиц и колонок модели данных."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from forge.modeling.domain.reserved_names import (
    LIQUIBASE_TABLES,
    POSTGRESQL_RESERVED_KEYWORDS,
    POSTGRESQL_SYSTEM_COLUMNS,
)
from forge.modeling.domain.violation import ModelViolationError, Violation

_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,62}")
_KEYWORDS = frozenset(POSTGRESQL_RESERVED_KEYWORDS)


@dataclass(frozen=True)
class Identifier:
    """Имя без кавычек: шаблон `^[a-z][a-z0-9_]{0,62}$`, не ключевое слово PostgreSQL.

    Нарушение сообщается с пустым путём: путь поля имени дописывает уровень выше.
    """

    value: str

    max_length: ClassVar[int] = 63
    forbidden: ClassVar[frozenset[str]] = frozenset()
    forbidden_reason: ClassVar[str] = ""

    def __post_init__(self) -> None:
        violation = self._violation()
        if violation is not None:
            raise ModelViolationError([violation])

    def _violation(self) -> Violation | None:
        if not _PATTERN.fullmatch(self.value):
            return Violation(
                "",
                "invalid_identifier",
                f"имя {self.value!r} не соответствует шаблону ^[a-z][a-z0-9_]{{0,62}}$",
            )
        if len(self.value) > self.max_length:
            return Violation(
                "",
                "invalid_identifier",
                f"имя {self.value!r} длиннее {self.max_length} символов",
            )
        if self.value in _KEYWORDS:
            return Violation(
                "",
                "reserved_identifier",
                f"имя {self.value!r} — зарезервированное слово PostgreSQL",
            )
        if self.value in self.forbidden:
            return Violation(
                "", "reserved_identifier", f"имя {self.value!r} — {self.forbidden_reason}"
            )
        return None

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TableName(Identifier):
    """Имя таблицы: не длиннее 60 символов, чтобы имя PK `pk_<таблица>` уложилось в 63."""

    max_length: ClassVar[int] = 60
    forbidden: ClassVar[frozenset[str]] = frozenset(LIQUIBASE_TABLES)
    forbidden_reason: ClassVar[str] = "таблица журнала Liquibase"


@dataclass(frozen=True)
class ColumnName(Identifier):
    """Имя колонки: не совпадает с системной колонкой PostgreSQL."""

    forbidden: ClassVar[frozenset[str]] = frozenset(POSTGRESQL_SYSTEM_COLUMNS)
    forbidden_reason: ClassVar[str] = "системная колонка PostgreSQL"
