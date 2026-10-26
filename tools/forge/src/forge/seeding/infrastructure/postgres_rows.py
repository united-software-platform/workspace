"""Чтение строк таблиц seed из PostgreSQL через `psycopg` в нормализованной форме seed.

Значение `psycopg` переводится в сырое значение того же вида, что даёт разборщик файла seed,
и приводится к типу колонки той же фабрикой `SeedValueFactory`: одна фабрика на обе стороны
сравнения, поэтому `numeric 1.50` и `"1.5"` из seed — одно значение. Значение, которое фабрика
не принимает, означает расхождение структуры с моделью — это ошибка окружения, а не вердикт.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from psycopg import sql

from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.table import Table
from forge.modeling.domain.violation import Violation
from forge.seeding.domain.draft import RawValue, ScalarKind
from forge.seeding.domain.seed import SeedRow
from forge.seeding.domain.seed_value import SeedValue, SeedValueFactory
from forge.shared.application.settings import DatabaseUnavailableError
from forge.shared.domain.target_database import TargetDatabase
from forge.shared.infrastructure.postgres import PostgresConnector

SCHEMA = "public"


def raw_value(value: object) -> RawValue:
    """Сырое значение seed для значения `psycopg`.

    `datetime` со смещением переводится в UTC, `Decimal` записывается без экспоненты: дальше
    форму выравнивает фабрика значений.
    """
    if value is None:
        return RawValue(ScalarKind.NULL, "null")
    if isinstance(value, bool):
        return RawValue(ScalarKind.BOOLEAN, "true" if value else "false")
    if isinstance(value, int):
        return RawValue(ScalarKind.INTEGER, str(value))
    if isinstance(value, Decimal):
        return RawValue(ScalarKind.STRING, format(value, "f"))
    if isinstance(value, datetime):
        moment = value.astimezone(UTC) if value.tzinfo is not None else value
        return RawValue(ScalarKind.STRING, moment.isoformat())
    if isinstance(value, date):
        return RawValue(ScalarKind.STRING, value.isoformat())
    if isinstance(value, UUID | str):
        return RawValue(ScalarKind.STRING, str(value))
    return RawValue(ScalarKind.OTHER, f"значение {type(value).__name__} {value!r}")


class PsycopgTableRowsReader:
    """Реализация чтения строк: `SELECT <колонки модели> FROM <таблица> ORDER BY <PK>`.

    Имена колонок и таблиц берутся из модели и экранируются как идентификаторы.
    """

    def __init__(
        self, connector: PostgresConnector, values: SeedValueFactory | None = None
    ) -> None:
        self._connector = connector
        self._values = values or SeedValueFactory()

    def rows(
        self, database: TargetDatabase, tables: Sequence[Table]
    ) -> dict[TableName, tuple[SeedRow, ...]]:
        fetched: dict[TableName, list[tuple[object, ...]]] = {}
        with self._connector.connect(database) as connection:
            for table in tables:
                fetched[table.name] = connection.execute(_query(table)).fetchall()
        return {
            table.name: tuple(self._row(database, table, values) for values in fetched[table.name])
            for table in tables
        }

    def _row(self, database: TargetDatabase, table: Table, values: tuple[object, ...]) -> SeedRow:
        normalized: list[tuple[ColumnName, SeedValue]] = []
        for column, value in zip(table.columns, values, strict=True):
            seed_value = self._values.create(column.type, raw_value(value))
            if isinstance(seed_value, Violation):
                raise DatabaseUnavailableError(
                    f"БД {database}: значение колонки {table.name}.{column.name} не приводится "
                    f"к типу модели {column.type}: {seed_value.message}"
                )
            normalized.append((column.name, seed_value))
        return SeedRow(tuple(normalized))


def _query(table: Table) -> sql.Composed:
    return sql.SQL("SELECT {columns} FROM {table} ORDER BY {key}").format(
        columns=sql.SQL(", ").join(sql.Identifier(c.name.value) for c in table.columns),
        table=sql.Identifier(SCHEMA, table.name.value),
        key=sql.SQL(", ").join(sql.Identifier(c.value) for c in table.primary_key.columns),
    )
