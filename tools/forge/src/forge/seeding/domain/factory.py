"""Фабрика seed: проверяет черновик по модели данных и строит агрегат.

Проверка идёт в порядке документа: имя таблицы и её повтор; для каждой строки — колонки
в порядке строки, затем пропущенные NOT NULL колонки в порядке модели; повторы первичного
ключа, затем повторы наборов `unique`. После таблиц проверяются ссылки внешних ключей и циклы.
"""

from __future__ import annotations

from collections.abc import Sequence

from forge.modeling.domain.column import Column
from forge.modeling.domain.data_model import DataModel
from forge.modeling.domain.identifier import ColumnName
from forge.modeling.domain.table import Table
from forge.modeling.domain.violation import Violation, join_path
from forge.seeding.domain.checked_rows import CheckedRow, CheckedTable
from forge.seeding.domain.draft import RowDraft, SeedDraft
from forge.seeding.domain.references import reference_violations
from forge.seeding.domain.seed import Seed, SeedTable, SeedViolationError
from forge.seeding.domain.seed_value import SeedValue, SeedValueFactory


class SeedFactory:
    """Строит seed из черновика; все нарушения сразу — `SeedViolationError`."""

    def __init__(self, values: SeedValueFactory | None = None) -> None:
        self._values = values or SeedValueFactory()

    def create(self, model: DataModel, draft: SeedDraft) -> Seed:
        tables, violations = self._tables(model, draft)
        violations += reference_violations(tables, frozenset(draft.excluded))
        if violations:
            raise SeedViolationError(violations)
        return Seed(
            tuple(
                SeedTable(checked.table, tuple(row.row(checked.table) for row in checked.rows))
                for checked in tables
            )
        )

    def _tables(
        self, model: DataModel, draft: SeedDraft
    ) -> tuple[list[CheckedTable], list[Violation]]:
        tables: list[CheckedTable] = []
        violations: list[Violation] = []
        first: dict[str, int] = {}
        for table_draft in draft.tables:
            path = f"tables[{table_draft.position}]"
            name = table_draft.name
            table = _model_table(model, name)
            if table is None:
                violations.append(
                    Violation(
                        join_path(path, "name"), "unknown_table", f"в модели нет таблицы {name}"
                    )
                )
                continue
            if name in first:
                violations.append(
                    Violation(
                        join_path(path, "name"),
                        "duplicate_table",
                        f"таблица {name} уже указана в tables[{first[name]}]",
                    )
                )
                continue
            first[name] = table_draft.position
            rows: list[CheckedRow] = []
            for index, row_draft in enumerate(table_draft.rows):
                row, found = self._row(table, join_path(path, f"rows[{index}]"), index, row_draft)
                rows.append(row)
                violations += found
            violations += _duplicate_keys(table, rows)
            tables.append(CheckedTable(table_draft.position, table, tuple(rows)))
        return tables, violations

    def _row(
        self, table: Table, path: str, position: int, draft: RowDraft
    ) -> tuple[CheckedRow, list[Violation]]:
        violations: list[Violation] = []
        values: dict[ColumnName, SeedValue] = {}
        complete = True
        written: set[str] = set()
        for key, raw in draft.values:
            written.add(key)
            column_path = join_path(path, key)
            column = _column(table, key)
            if column is None:
                violations.append(
                    Violation(
                        column_path, "unknown_column", f"в таблице {table.name} нет колонки {key}"
                    )
                )
                continue
            value = self._values.create(column.type, raw)
            if isinstance(value, Violation):
                violations.append(value.under(column_path))
                complete = False
            elif value.is_null() and not table.is_nullable(column.name):
                violations.append(_null_value(table, column, column_path, "указан null"))
                complete = False
            elif (violation := _check_violation(column, value)) is not None:
                violations.append(violation.under(column_path))
                complete = False
            else:
                values[column.name] = value
        for column in table.columns:
            if column.name.value in written:
                continue
            if table.is_nullable(column.name):
                values[column.name] = SeedValue.null()
            else:
                path_of = join_path(path, column.name.value)
                violations.append(_null_value(table, column, path_of, "значение не указано"))
                complete = False
        return CheckedRow(position, path, values, complete), violations


def _model_table(model: DataModel, name: str) -> Table | None:
    return next((table for table in model.tables if table.name.value == name), None)


def _column(table: Table, name: str) -> Column | None:
    return next((column for column in table.columns if column.name.value == name), None)


def _check_violation(column: Column, value: SeedValue) -> Violation | None:
    """Нарушение перечня значений колонки; NULL и колонка без перечня перечню не подчинены."""
    if column.check is None or value.is_null():
        return None
    if (type(value.value), value.value) in column.check.composition():
        return None
    allowed = ", ".join(str(item) for item in column.check.sorted_values())
    return Violation(
        "",
        "check_violated",
        f"значение {value} колонки {column.name} не входит в перечень: {allowed}",
    )


def _null_value(table: Table, column: Column, path: str, reason: str) -> Violation:
    role = "входит в первичный ключ" if column.name in table.primary_key else "NOT NULL"
    return Violation(
        path,
        "null_value",
        f"колонка {column.name} {role} и требует значения: {reason}",
    )


def _duplicate_keys(table: Table, rows: Sequence[CheckedRow]) -> list[Violation]:
    """Повторы первичного ключа, затем повторы каждого набора `unique` в порядке модели.

    Строка с нарушенным значением не участвует; строка с NULL в наборе — тоже, как в PostgreSQL.
    """
    violations = _repeats(table, rows, table.primary_key.columns, "duplicate_primary_key")
    for unique in table.unique:
        violations += _repeats(table, rows, unique.columns, "duplicate_unique")
    return violations


def _repeats(
    table: Table, rows: Sequence[CheckedRow], columns: tuple[ColumnName, ...], code: str
) -> list[Violation]:
    what = "первичный ключ" if code == "duplicate_primary_key" else "набор unique"
    first: dict[tuple[SeedValue, ...], CheckedRow] = {}
    violations: list[Violation] = []
    for row in rows:
        key = row.key(columns) if row.complete else None
        if key is None or any(value.is_null() for value in key):
            continue
        if key in first:
            pairs = ", ".join(f"{c}={v}" for c, v in zip(columns, key, strict=True))
            violations.append(
                Violation(
                    row.path,
                    code,
                    f"{what} [{pairs}] таблицы {table.name} уже задан строкой {first[key].path}",
                )
            )
        else:
            first[key] = row
    return violations
