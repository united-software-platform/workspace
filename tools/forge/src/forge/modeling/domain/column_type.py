"""Тип колонки модели данных: перечень формата и параметры типа."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from forge.modeling.domain.violation import ModelViolationError, Violation

# Пределы взяты у PostgreSQL — единственной СУБД первой поставки:
# varchar(n) допускает n до 10485760, numeric — точность до 1000
MAX_STRING_LENGTH = 10_485_760
MAX_DECIMAL_PRECISION = 1000


class TypeKind(StrEnum):
    """Тип колонки из перечня формата, а не тип СУБД."""

    INTEGER = "integer"
    BIGINT = "bigint"
    BOOLEAN = "boolean"
    STRING = "string"
    TEXT = "text"
    DECIMAL = "decimal"
    DATE = "date"
    TIMESTAMP = "timestamp"
    TIMESTAMP_TZ = "timestamp_tz"
    UUID = "uuid"


_PARAMETERS: dict[TypeKind, tuple[str, ...]] = {
    TypeKind.STRING: ("length",),
    TypeKind.DECIMAL: ("precision", "scale"),
}
_ALL_PARAMETERS = ("length", "precision", "scale")


@dataclass(frozen=True)
class ColumnType:
    """Тип колонки с параметрами: `length` у `string`, `precision` и `scale` у `decimal`.

    Конструктор сообщает все нарушения типа сразу, с путями относительно колонки:
    `type`, `length`, `precision`, `scale`.
    """

    kind: TypeKind
    length: int | None = None
    precision: int | None = None
    scale: int | None = None

    def __post_init__(self) -> None:
        violations = list(self._parameter_violations())
        if violations:
            raise ModelViolationError(violations)

    def __str__(self) -> str:
        """Тип в записи формата: `string(255)`, `decimal(12, 2)`, `uuid`."""
        values = [str(value) for value in self.parameters().values() if value is not None]
        return f"{self.kind.value}({', '.join(values)})" if values else self.kind.value

    def parameters(self) -> dict[str, int | None]:
        """Параметры типа по именам полей файла модели."""
        return {"length": self.length, "precision": self.precision, "scale": self.scale}

    def _parameter_violations(self) -> list[Violation]:
        expected = _PARAMETERS.get(self.kind, ())
        values = self.parameters()
        violations = [
            Violation(name, "unexpected_type_parameter", f"у типа {self.kind} нет параметра {name}")
            for name in _ALL_PARAMETERS
            if name not in expected and values[name] is not None
        ]
        violations += [
            Violation(name, "missing_type_parameter", f"у типа {self.kind} обязателен {name}")
            for name in expected
            if values[name] is None
        ]
        if self.kind is TypeKind.STRING:
            violations += _range("length", self.length, 1, MAX_STRING_LENGTH)
        if self.kind is TypeKind.DECIMAL:
            violations += _range("precision", self.precision, 1, MAX_DECIMAL_PRECISION)
            if self.precision is not None and 1 <= self.precision <= MAX_DECIMAL_PRECISION:
                violations += _range("scale", self.scale, 0, self.precision)
            elif self.scale is not None and self.scale < 0:
                violations += _range("scale", self.scale, 0, MAX_DECIMAL_PRECISION)
        return violations


def _range(name: str, value: int | None, low: int, high: int) -> list[Violation]:
    if value is None or low <= value <= high:
        return []
    return [
        Violation(
            name,
            "type_parameter_out_of_range",
            f"{name} должен быть от {low} до {high}, получено {value}",
        )
    ]


def parse_column_type(
    name: str,
    *,
    length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
) -> ColumnType:
    """Построить тип по имени из файла модели; неизвестное имя — нарушение `unknown_type`."""
    try:
        kind = TypeKind(name)
    except ValueError:
        allowed = ", ".join(kind.value for kind in TypeKind)
        raise ModelViolationError(
            [Violation("type", "unknown_type", f"тип {name!r} не входит в перечень: {allowed}")]
        ) from None
    return ColumnType(kind, length=length, precision=precision, scale=scale)
