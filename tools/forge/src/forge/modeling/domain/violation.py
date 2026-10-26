"""Нарушение модели данных и исключение, которое несёт все нарушения сразу."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """Одно нарушение модели: путь в файле модели, код из перечня формата и сообщение.

    Путь строится от места проверки: объект-значение сообщает путь относительно себя
    (`length`), а уровень выше дописывает свой префикс (`columns[1].length`).
    Пустой путь означает весь документ.
    """

    path: str
    code: str
    message: str

    def under(self, prefix: str) -> Violation:
        """То же нарушение с путём, вложенным в `prefix`."""
        return Violation(join_path(prefix, self.path), self.code, self.message)


def join_path(prefix: str, path: str) -> str:
    """Соединить префикс и путь: `tables[0]` и `columns[1]` дают `tables[0].columns[1]`."""
    if not prefix:
        return path
    if not path:
        return prefix
    if path.startswith("["):
        return prefix + path
    return f"{prefix}.{path}"


class ModelViolationError(Exception):
    """Модель или её часть нарушает инварианты: объект не создан, нарушения перечислены."""

    def __init__(self, violations: Iterable[Violation]) -> None:
        self.violations: tuple[Violation, ...] = tuple(violations)
        if not self.violations:
            raise ValueError("ModelViolationError требует хотя бы одного нарушения")
        super().__init__("; ".join(f"{v.path}: {v.message}" for v in self.violations))

    def under(self, prefix: str) -> ModelViolationError:
        """То же исключение с путями нарушений, вложенными в `prefix`."""
        return ModelViolationError(violation.under(prefix) for violation in self.violations)
