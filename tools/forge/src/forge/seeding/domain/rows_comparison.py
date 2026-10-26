"""Сравнение фактических строк таблиц seed с seed попытки по первичному ключу."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from forge.modeling.domain.identifier import TableName
from forge.modeling.domain.table import Table
from forge.reconciliation.domain.discrepancy import Discrepancy, RowKey
from forge.seeding.domain.seed import Seed, SeedRow
from forge.seeding.domain.seed_value import SeedValue

PRESENT = "present"
ABSENT = "absent"


class SeedRowsComparison:
    """Доменный сервис: расхождения строк таблиц seed с seed попытки.

    Строки сопоставляются по первичному ключу в нормализованной форме, значения сравниваются
    по всем колонкам модели: колонка без ключа в seed хранится как NULL. Таблица seed
    принадлежит ему целиком, поэтому строка БД с ключом вне seed — лишняя. Таблица, убранная
    из seed, ожидается пустой.

    Порядок: таблицы seed попытки в порядке seed; внутри таблицы — строки seed по порядку
    с `row_missing` либо `value_mismatch` по колонкам модели, затем лишние строки в порядке
    фактических строк; затем убранные таблицы в переданном порядке. Фактические строки
    передаются по возрастанию первичного ключа, поэтому перечень устойчив.
    """

    def compare(
        self,
        attempt: Seed,
        removed: Sequence[Table],
        actual: Mapping[TableName, Sequence[SeedRow]],
    ) -> tuple[Discrepancy, ...]:
        discrepancies: list[Discrepancy] = []
        for seed_table in attempt.tables:
            discrepancies += _table(seed_table.table, seed_table.rows, actual[seed_table.name])
        for table in removed:
            discrepancies += _table(table, (), actual[table.name], removed=True)
        return tuple(discrepancies)


def _table(
    table: Table, expected: Sequence[SeedRow], actual: Sequence[SeedRow], removed: bool = False
) -> list[Discrepancy]:
    columns = table.primary_key.columns
    found = {row.key(columns): row for row in actual}
    discrepancies: list[Discrepancy] = []
    for row in expected:
        fact = found.get(row.key(columns))
        if fact is None:
            discrepancies.append(_missing(table, row))
        else:
            discrepancies += _mismatches(table, row, fact)
    keys = {row.key(columns) for row in expected}
    discrepancies += [
        _unexpected(table, row, removed) for row in actual if row.key(columns) not in keys
    ]
    return discrepancies


def _missing(table: Table, row: SeedRow) -> Discrepancy:
    return Discrepancy(
        "row_missing",
        table.name.value,
        None,
        None,
        PRESENT,
        ABSENT,
        f"строки {_label(table, row)} нет в БД",
        _key(table, row),
    )


def _mismatches(table: Table, expected: SeedRow, actual: SeedRow) -> list[Discrepancy]:
    discrepancies: list[Discrepancy] = []
    for column in table.columns:
        want, got = expected.value(column.name), actual.value(column.name)
        if want == got:
            continue
        discrepancies.append(
            Discrepancy(
                "value_mismatch",
                table.name.value,
                column.name.value,
                None,
                str(want),
                str(got),
                f"значение {_label(table, expected)}.{column.name}: "
                f"ожидалось {_quoted(want)}, в БД {_quoted(got)}",
                _key(table, expected),
            )
        )
    return discrepancies


def _unexpected(table: Table, row: SeedRow, removed: bool) -> Discrepancy:
    reason = (
        f"таблица {table.name} убрана из seed и должна быть пуста"
        if removed
        else "в seed попытки её нет"
    )
    return Discrepancy(
        "row_unexpected",
        table.name.value,
        None,
        None,
        ABSENT,
        _pairs(row.values),
        f"лишняя строка {_label(table, row)}: {reason}",
        _key(table, row),
    )


def _key(table: Table, row: SeedRow) -> RowKey:
    return tuple((column.value, row.value(column).value) for column in table.primary_key.columns)


def _label(table: Table, row: SeedRow) -> str:
    pairs = tuple((column, row.value(column)) for column in table.primary_key.columns)
    return f"{table.name}{_pairs(pairs)}"


def _pairs(values: Sequence[tuple[object, SeedValue]]) -> str:
    """Пары «колонка=значение» для ожидаемого и сообщений: `[code=draft, title=Черновик]`."""
    return "[" + ", ".join(f"{column}={value}" for column, value in values) + "]"


def _quoted(value: SeedValue) -> str:
    return "null" if value.is_null() else repr(str(value))
