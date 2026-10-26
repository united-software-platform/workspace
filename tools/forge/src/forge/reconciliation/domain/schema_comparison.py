"""Сравнение фактической схемы с моделью данных."""

from __future__ import annotations

from forge.modeling.domain.data_model import DataModel
from forge.modeling.domain.table import Table
from forge.reconciliation.domain.actual_schema import ActualForeignKey, ActualSchema, ActualTable
from forge.reconciliation.domain.discrepancy import Discrepancy

ABSENT = "absent"
PRESENT = "present"


class SchemaComparison:
    """Доменный сервис: расхождения фактической схемы с моделью в устойчивом порядке.

    Таблицы модели — по порядку, внутри таблицы: колонки модели, лишние колонки по имени,
    первичный ключ, наборы уникальности модели, лишние наборы, внешние ключи модели, лишние
    внешние ключи. Затем лишние таблицы по имени. Порядок колонок и имена ограничений
    не сравниваются; наборы сравниваются по составу, внешние ключи — по целевой таблице
    и парам колонок. Лишние ограничения идут в порядке их записи колонками.
    """

    def compare(self, model: DataModel, actual: ActualSchema) -> tuple[Discrepancy, ...]:
        discrepancies: list[Discrepancy] = []
        for table in model.tables:
            name = table.name.value
            found = actual.table(name)
            if found is None:
                discrepancies.append(
                    _table("table_missing", name, PRESENT, ABSENT, f"таблицы {name} нет в БД")
                )
                continue
            discrepancies += _table_discrepancies(table, found)
        known = {table.name.value for table in model.tables}
        for extra in sorted(t.name for t in actual.tables if t.name not in known):
            discrepancies.append(
                _table("table_unexpected", extra, ABSENT, PRESENT, f"в БД лишняя таблица {extra}")
            )
        return tuple(discrepancies)


def _table_discrepancies(table: Table, actual: ActualTable) -> list[Discrepancy]:
    name = table.name.value
    result: list[Discrepancy] = []
    for column in table.columns:
        column_name = column.name.value
        found = actual.column(column_name)
        expected_type = str(column.type)
        if found is None:
            result.append(
                _column(
                    "column_missing",
                    name,
                    column_name,
                    expected_type,
                    ABSENT,
                    f"колонки {name}.{column_name} нет в БД",
                )
            )
            continue
        if found.type != column.type:
            result.append(
                _column(
                    "column_type_mismatch",
                    name,
                    column_name,
                    expected_type,
                    found.type_text,
                    f"тип колонки {name}.{column_name}: ожидался {expected_type}, "
                    f"в БД {found.type_text}",
                )
            )
        expected_nullable = table.is_nullable(column.name)
        if found.nullable != expected_nullable:
            result.append(
                _column(
                    "column_nullable_mismatch",
                    name,
                    column_name,
                    _nullable(expected_nullable),
                    _nullable(found.nullable),
                    f"колонка {name}.{column_name}: ожидалось {_nullable(expected_nullable)}, "
                    f"в БД {_nullable(found.nullable)}",
                )
            )
    known = {column.name.value for column in table.columns}
    for extra_column in sorted(
        (c for c in actual.columns if c.name not in known), key=lambda c: c.name
    ):
        result.append(
            _column(
                "column_unexpected",
                name,
                extra_column.name,
                ABSENT,
                extra_column.type_text,
                f"в таблице {name} лишняя колонка {extra_column.name}",
            )
        )
    expected_key = [column.value for column in table.primary_key.columns]
    actual_key = list(actual.primary_key) if actual.primary_key is not None else None
    if actual_key != expected_key:
        shown = _key(actual_key) if actual_key is not None else ABSENT
        result.append(
            _table(
                "primary_key_mismatch",
                name,
                _key(expected_key),
                shown,
                f"первичный ключ таблицы {name}: ожидался {_key(expected_key)}, в БД {shown}",
            )
        )
    return result + _unique_discrepancies(table, actual) + _foreign_key_discrepancies(table, actual)


def _unique_discrepancies(table: Table, actual: ActualTable) -> list[Discrepancy]:
    name = table.name.value
    present = {frozenset(columns) for columns in actual.unique}
    known: set[frozenset[str]] = set()
    result: list[Discrepancy] = []
    for unique in table.unique:
        columns = [column.value for column in unique.columns]
        known.add(frozenset(columns))
        if frozenset(columns) not in present:
            shown = _key(columns)
            result.append(
                _table(
                    "unique_missing",
                    name,
                    shown,
                    ABSENT,
                    f"набора уникальности {name}{shown} нет в БД",
                )
            )
    extras = sorted(
        _key(list(columns)) for columns in actual.unique if frozenset(columns) not in known
    )
    for shown in extras:
        result.append(
            _table(
                "unique_unexpected",
                name,
                ABSENT,
                shown,
                f"в таблице {name} лишнее ограничение уникальности {shown}",
            )
        )
    return result


def _foreign_key_discrepancies(table: Table, actual: ActualTable) -> list[Discrepancy]:
    name = table.name.value
    present = {_actual_identity(key) for key in actual.foreign_keys}
    result: list[Discrepancy] = []
    expected: set[tuple[str, frozenset[tuple[str, str]]]] = set()
    for key in table.foreign_keys:
        identity = (key.target.value, frozenset((a.value, b.value) for a, b in key.pairs()))
        expected.add(identity)
        if identity not in present:
            result.append(
                _table(
                    "foreign_key_missing",
                    name,
                    str(key),
                    ABSENT,
                    f"внешнего ключа {name} {key} нет в БД",
                )
            )
    extras = sorted(
        str(key) for key in actual.foreign_keys if _actual_identity(key) not in expected
    )
    for shown in extras:
        result.append(
            _table(
                "foreign_key_unexpected",
                name,
                ABSENT,
                shown,
                f"в таблице {name} лишний внешний ключ {shown}",
            )
        )
    return result


def _actual_identity(key: ActualForeignKey) -> tuple[str, frozenset[tuple[str, str]]]:
    return key.target, key.pairs()


def _table(kind: str, table: str, expected: str, actual: str, message: str) -> Discrepancy:
    return Discrepancy(kind, table, None, None, expected, actual, message)


def _column(
    kind: str, table: str, column: str, expected: str, actual: str, message: str
) -> Discrepancy:
    return Discrepancy(kind, table, column, None, expected, actual, message)


def _nullable(nullable: bool) -> str:
    return "NULL" if nullable else "NOT NULL"


def _key(columns: list[str]) -> str:
    return "[" + ", ".join(columns) + "]"
