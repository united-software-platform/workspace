"""Выходной контракт сценария построения changelog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChangeSetView:
    """Changeset в ответе: `id`, вид, таблица, колонка для `add_column` и `drop_column`
    и имя ограничения для видов набора уникальности и внешнего ключа."""

    id: str
    kind: str
    table: str
    column: str | None
    constraint: str | None = None


@dataclass(frozen=True)
class ModelViolationView:
    """Нарушение формата модели попытки."""

    path: str
    code: str
    message: str


@dataclass(frozen=True)
class UnsupportedChangeView:
    """Неподдерживаемое изменение модели попытки: смена типа, NULL или первичного ключа."""

    code: str
    table: str
    column: str | None
    message: str


@dataclass(frozen=True)
class SeedConflictView:
    """Конфликт модели попытки с принятым seed."""

    kind: str
    table: str
    column: str | None
    path: str
    message: str


@dataclass(frozen=True)
class GenerateChangelogOutput:
    """Итог: путь changelog при успехе, иначе нарушения модели, неподдерживаемые изменения
    или конфликты с принятым seed."""

    changelog_path: str | None
    logical_file_path: str
    changesets: tuple[ChangeSetView, ...]
    violations: tuple[ModelViolationView, ...]
    non_additive: tuple[UnsupportedChangeView, ...]
    generated: bool
    seed_conflict: tuple[SeedConflictView, ...] = ()
