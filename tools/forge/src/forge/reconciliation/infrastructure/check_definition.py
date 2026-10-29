"""Перевод определения `CHECK` из `pg_get_constraintdef` в колонку и перечень значений.

Anti-Corruption Layer Сверки: PostgreSQL хранит `CHECK (source IN ('a', 'b'))` в нормализованном
виде, и форма зависит от типа колонки:

- `CHECK ((source = ANY (ARRAY['a'::text, 'b'::text])))` — `text`;
- `CHECK (((source)::text = ANY ((ARRAY['a'::character varying, …])::text[])))` — `varchar`;
- `CHECK ((priority = ANY (ARRAY[1, 2])))` — `integer`, у `bigint` элементы `(1)::bigint`,
  `'3000000000'::bigint` и `('-5'::integer)::bigint`;
- `CHECK (((source)::text = 'a'::text))` — перечень из одного значения сворачивается в `=`.

Распознаётся только сравнение одной колонки с перечнем литералов. Прочее — выражение,
несколько колонок, функция — даёт `None`: Сверка считает такое ограничение лишним.
"""

from __future__ import annotations

import re

from forge.reconciliation.domain.actual_schema import ActualCheck, CheckValue

_IDENTIFIER = r"[a-z][a-z0-9_]*"
_COLUMN = re.compile(rf"\(*({_IDENTIFIER})\)*(?:::[a-z ]+)?")
_STRING_CASTS = frozenset({"text", "character varying"})
_INTEGER_CASTS = frozenset({"integer", "bigint"})
# Литерал с приведением; у `bigint` отрицательное значение приводится дважды:
# `('-5'::integer)::bigint` — значимо внешнее приведение
_ELEMENT = re.compile(r"\(?('(?:[^']|'')*'|-?\d+)(?:::([a-z ]+))?\)?(?:::([a-z ]+))?")
_ARRAY = re.compile(r"\(*ARRAY\[(.*?)\]\)*(?:::[a-z ]+\[\])?", re.S)


def parse_check(definition: str, columns: tuple[str, ...]) -> ActualCheck:
    """Ограничение по определению и колонкам `conkey`; нераспознанное — без колонки и значений."""
    unknown = ActualCheck(definition)
    if len(columns) != 1:
        return unknown
    body = _unwrap(definition.removeprefix("CHECK ")) if definition.startswith("CHECK ") else None
    if body is None:
        return unknown
    left, separator, right = body.partition(" = ")
    column = _COLUMN.fullmatch(left.strip())
    if not separator or column is None or column[1] != columns[0]:
        return unknown
    values = _values(right.strip())
    if values is None or not values:
        return unknown
    return ActualCheck(definition, column[1], frozenset(values))


def _values(text: str) -> list[CheckValue] | None:
    if text.startswith("ANY "):
        inner = _unwrap(text.removeprefix("ANY "))
        array = _ARRAY.fullmatch(inner) if inner is not None else None
        if array is None:
            return None
        elements = _split(array[1])
        if elements is None:
            return None
        values = [_element(element) for element in elements]
        return (
            None if any(value is None for value in values) else [v for v in values if v is not None]
        )
    value = _element(text)
    return None if value is None else [value]


def _element(text: str) -> CheckValue | None:
    match = _ELEMENT.fullmatch(text.strip())
    if match is None:
        return None
    literal, cast = match[1], match[3] or match[2]
    if literal.startswith("'"):
        content = literal[1:-1].replace("''", "'")
        if cast in _INTEGER_CASTS:
            return int(content) if re.fullmatch(r"-?\d+", content) else None
        return content if cast in _STRING_CASTS else None
    return int(literal) if cast is None or cast in _INTEGER_CASTS else None


def _unwrap(text: str) -> str | None:
    """Содержимое внешних скобок, охватывающих весь текст, снятых все до последних."""
    text = text.strip()
    if not _enclosed(text):
        return None
    while _enclosed(text):
        text = text[1:-1].strip()
    return text


def _enclosed(text: str) -> bool:
    """Охватывает ли первая скобка весь текст: `(a) = (b)` — нет, `((a) = b)` — да."""
    if not text.startswith("(") or not text.endswith(")"):
        return False
    depth = 0
    quoted = False
    for position, char in enumerate(text):
        if char == "'":
            quoted = not quoted
        elif not quoted and char == "(":
            depth += 1
        elif not quoted and char == ")":
            depth -= 1
            if depth == 0 and position != len(text) - 1:
                return False
    return depth == 0 and not quoted


def _split(text: str) -> list[str] | None:
    """Элементы массива по запятым верхнего уровня вне кавычек и скобок."""
    elements: list[str] = []
    depth = 0
    quoted = False
    start = 0
    for position, char in enumerate(text):
        if char == "'":
            quoted = not quoted
        elif not quoted and char in "([":
            depth += 1
        elif not quoted and char in ")]":
            depth -= 1
        elif not quoted and depth == 0 and char == ",":
            elements.append(text[start:position])
            start = position + 1
    if quoted or depth != 0:
        return None
    elements.append(text[start:])
    return elements
