"""Значение колонки строки seed в нормализованной форме и его фабрика по типу колонки."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from forge.modeling.domain.column_type import ColumnType, TypeKind
from forge.modeling.domain.violation import Violation
from forge.seeding.domain.draft import RawValue, ScalarKind

INTEGER_RANGES = {
    TypeKind.INTEGER: (-(2**31), 2**31 - 1),
    TypeKind.BIGINT: (-(2**63), 2**63 - 1),
}

_INTEGER = re.compile(r"-?[0-9]+")
_DECIMAL = re.compile(r"([+-]?)([0-9]+)(?:\.([0-9]+))?")
_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_TIME = r"T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{1,6}))?"
_TIMESTAMP = re.compile(_DATE.pattern + _TIME)
_TIMESTAMP_TZ = re.compile(_DATE.pattern + _TIME + r"(Z|[+-][0-9]{2}:[0-9]{2})")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

_DATE_KINDS = frozenset({ScalarKind.STRING, ScalarKind.TIMESTAMP})


@dataclass(frozen=True)
class SeedValue:
    """Значение колонки в нормализованной форме; `None` — NULL.

    Форма зависит от типа колонки: целое у `integer` и `bigint`, `True`/`False` у `boolean`,
    строка у остальных типов — десятичная запись без лишних нулей, дата и момент в ISO 8601,
    момент `timestamp_tz` в UTC с суффиксом `Z`. Равенство — по форме: `"1.50"` и `"1.5"`
    одной колонки `decimal` — одно значение. Сравниваются значения колонок одного типа.
    """

    value: int | bool | str | None

    @staticmethod
    def null() -> SeedValue:
        return SeedValue(None)

    def is_null(self) -> bool:
        return self.value is None

    def __str__(self) -> str:
        """Форма для сообщений: `10`, `true`, `draft`, `null`."""
        if self.value is None:
            return "null"
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        return str(self.value)


class SeedValueFactory:
    """Строит значение по типу колонки модели из сырого значения файла seed.

    Неверное значение — нарушение с пустым путём вместо значения: путь колонки дописывает
    уровень выше. Вид значения не приводится: число в строковой колонке, строка в целой
    и дробное число YAML в `decimal` — `invalid_value`.
    """

    def create(self, column_type: ColumnType, raw: RawValue) -> SeedValue | Violation:
        if raw.kind is ScalarKind.NULL:
            return SeedValue.null()
        kind = column_type.kind
        if kind in INTEGER_RANGES:
            return _integer(column_type, raw)
        if kind is TypeKind.BOOLEAN:
            if raw.kind is not ScalarKind.BOOLEAN:
                return _invalid(column_type, raw, "логическое значение true или false")
            return SeedValue(raw.text == "true")
        if kind in (TypeKind.STRING, TypeKind.TEXT):
            return _string(column_type, raw)
        if kind is TypeKind.DECIMAL:
            return _decimal(column_type, raw)
        if kind is TypeKind.DATE:
            return _date(column_type, raw)
        if kind in (TypeKind.TIMESTAMP, TypeKind.TIMESTAMP_TZ):
            return _timestamp(column_type, raw)
        return _uuid(column_type, raw)


def _integer(column_type: ColumnType, raw: RawValue) -> SeedValue | Violation:
    if raw.kind is not ScalarKind.INTEGER or not _INTEGER.fullmatch(raw.text):
        return _invalid(column_type, raw, "целое число YAML без кавычек")
    value = int(raw.text)
    low, high = INTEGER_RANGES[column_type.kind]
    if not low <= value <= high:
        return _out_of_range(f"значение {value} вне диапазона {column_type}: от {low} до {high}")
    return SeedValue(value)


def _string(column_type: ColumnType, raw: RawValue) -> SeedValue | Violation:
    if raw.kind is not ScalarKind.STRING:
        return _invalid(column_type, raw, "строка; число и логическое значение берутся в кавычки")
    length = column_type.length
    if length is not None and len(raw.text) > length:
        return _out_of_range(
            f"строка длиной {len(raw.text)} символов длиннее {column_type}: не больше {length}"
        )
    return SeedValue(raw.text)


def _decimal(column_type: ColumnType, raw: RawValue) -> SeedValue | Violation:
    match = _DECIMAL.fullmatch(raw.text)
    if raw.kind not in (ScalarKind.STRING, ScalarKind.INTEGER) or match is None:
        return _invalid(
            column_type, raw, 'десятичная запись строкой, например "-12.50", или целое число'
        )
    sign, whole, fraction = match.group(1), match.group(2).lstrip("0"), match.group(3) or ""
    fraction = fraction.rstrip("0")
    precision = column_type.precision or 0
    scale = column_type.scale or 0
    if len(whole) > precision - scale or len(fraction) > scale:
        return _out_of_range(
            f"значение {raw.text} не помещается в {column_type}: "
            f"до {precision - scale} цифр целой части и до {scale} цифр дробной"
        )
    negative = sign == "-" and bool(whole or fraction)
    form = ("-" if negative else "") + (whole or "0") + (f".{fraction}" if fraction else "")
    return SeedValue(form)


def _date(column_type: ColumnType, raw: RawValue) -> SeedValue | Violation:
    match = _DATE.fullmatch(raw.text)
    if raw.kind not in _DATE_KINDS or match is None:
        return _invalid(column_type, raw, "дата вида YYYY-MM-DD")
    try:
        value = date(*(int(part) for part in match.groups()))
    except ValueError:
        return _invalid(column_type, raw, "существующая календарная дата")
    return SeedValue(value.isoformat())


def _timestamp(column_type: ColumnType, raw: RawValue) -> SeedValue | Violation:
    with_zone = column_type.kind is TypeKind.TIMESTAMP_TZ
    pattern = _TIMESTAMP_TZ if with_zone else _TIMESTAMP
    expected = (
        "момент вида YYYY-MM-DDTHH:MM:SS с дробью до шести знаков и смещением Z или ±HH:MM"
        if with_zone
        else "момент вида YYYY-MM-DDTHH:MM:SS с дробью до шести знаков, без смещения"
    )
    match = pattern.fullmatch(raw.text)
    if raw.kind not in _DATE_KINDS or match is None:
        return _invalid(column_type, raw, expected)
    year, month, day, hour, minute, second = (int(part) for part in match.groups()[:6])
    micro = int((match.group(7) or "").ljust(6, "0"))
    try:
        moment = datetime(year, month, day, hour, minute, second, micro)
        if with_zone:
            moment = (
                moment.replace(tzinfo=_zone(match.group(8))).astimezone(UTC).replace(tzinfo=None)
            )
    except (ValueError, OverflowError):
        return _invalid(column_type, raw, "существующие дата, время и смещение")
    form = moment.strftime("%Y-%m-%dT%H:%M:%S")
    if moment.microsecond:
        form += f".{moment.microsecond:06d}".rstrip("0")
    return SeedValue(form + ("Z" if with_zone else ""))


def _zone(offset: str) -> timezone:
    if offset == "Z":
        return UTC
    hours, minutes = int(offset[1:3]), int(offset[4:6])
    if minutes > 59:
        raise ValueError(offset)
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(-delta if offset[0] == "-" else delta)


def _uuid(column_type: ColumnType, raw: RawValue) -> SeedValue | Violation:
    if raw.kind is not ScalarKind.STRING or not _UUID.fullmatch(raw.text):
        return _invalid(column_type, raw, "UUID строкой в нижнем регистре по схеме 8-4-4-4-12")
    return SeedValue(raw.text)


def _invalid(column_type: ColumnType, raw: RawValue, expected: str) -> Violation:
    return Violation(
        "",
        "invalid_value",
        f"колонка типа {column_type} ожидает: {expected}; получено: {raw.describe()}",
    )


def _out_of_range(message: str) -> Violation:
    return Violation("", "value_out_of_range", message)
