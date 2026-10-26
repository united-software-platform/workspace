"""Интроспекция каталога PostgreSQL и журнала Liquibase через `psycopg`.

Обратное отображение типов PostgreSQL в типы модели — Anti-Corruption Layer: домен Сверки
сравнивает типы модели, а не строки СУБД. Тип вне формата остаётся `None`, его исходная запись
сохраняется для расхождения.
"""

from __future__ import annotations

import re

from forge.modeling.domain.column_type import ColumnType, TypeKind
from forge.reconciliation.domain.actual_schema import (
    ActualColumn,
    ActualForeignKey,
    ActualSchema,
    ActualTable,
)
from forge.reconciliation.domain.journal_check import JournalRecord
from forge.shared.domain.target_database import TargetDatabase
from forge.shared.infrastructure.postgres import PostgresConnector

LIQUIBASE_TABLES = ("databasechangelog", "databasechangeloglock")

_PLAIN: dict[str, TypeKind] = {
    "integer": TypeKind.INTEGER,
    "bigint": TypeKind.BIGINT,
    "boolean": TypeKind.BOOLEAN,
    "text": TypeKind.TEXT,
    "date": TypeKind.DATE,
    "uuid": TypeKind.UUID,
    "timestamp without time zone": TypeKind.TIMESTAMP,
    "timestamp with time zone": TypeKind.TIMESTAMP_TZ,
}
_VARCHAR = re.compile(r"character varying\((\d+)\)")
_NUMERIC = re.compile(r"numeric\((\d+),(\d+)\)")

_COLUMNS = """
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT (c.relname = ANY(%s))
ORDER BY c.relname, a.attnum
"""
_TABLES = """
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT (c.relname = ANY(%s))
ORDER BY c.relname
"""
_KEYS = """
SELECT c.relname, array_agg(a.attname ORDER BY k.ordinality)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality)
JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
WHERE n.nspname = 'public' AND con.contype = 'p'
GROUP BY c.relname
"""
# Номера колонок `conkey` и `confkey` раскрываются в имена через `pg_attribute` с сохранением
# порядка: у FK он задаёт пары «колонка FK → колонка цели»
_CONSTRAINTS = """
SELECT c.relname, con.contype,
  ARRAY(
    SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality)
    JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
    ORDER BY k.ordinality
  ),
  t.relname,
  ARRAY(
    SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY AS k(attnum, ordinality)
    JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum
    ORDER BY k.ordinality
  )
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_class t ON t.oid = con.confrelid
WHERE n.nspname = 'public' AND con.contype IN ('f', 'u') AND NOT (c.relname = ANY(%s))
ORDER BY c.relname, con.conname
"""


def model_type(database_type: str) -> ColumnType | None:
    """Тип модели по записи `format_type`; `None`, если формат такого типа не знает."""
    if database_type in _PLAIN:
        return ColumnType(_PLAIN[database_type])
    if match := _VARCHAR.fullmatch(database_type):
        return ColumnType(TypeKind.STRING, length=int(match[1]))
    if match := _NUMERIC.fullmatch(database_type):
        return ColumnType(TypeKind.DECIMAL, precision=int(match[1]), scale=int(match[2]))
    return None


class PsycopgSchemaIntrospector:
    """Реализация интроспекции схемы `public` по `pg_catalog`."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def read(self, database: TargetDatabase) -> ActualSchema:
        excluded = list(LIQUIBASE_TABLES)
        with self._connector.connect(database) as connection:
            names = [row[0] for row in connection.execute(_TABLES, (excluded,)).fetchall()]
            columns = connection.execute(_COLUMNS, (excluded,)).fetchall()
            keys = {row[0]: tuple(row[1]) for row in connection.execute(_KEYS).fetchall()}
            constraints = connection.execute(_CONSTRAINTS, (excluded,)).fetchall()
        by_table: dict[str, list[ActualColumn]] = {name: [] for name in names}
        for table, name, database_type, not_null in columns:
            by_table[table].append(
                ActualColumn(name, model_type(database_type), database_type, not not_null)
            )
        unique: dict[str, list[tuple[str, ...]]] = {name: [] for name in names}
        foreign_keys: dict[str, list[ActualForeignKey]] = {name: [] for name in names}
        for table, kind, own, target, target_columns in constraints:
            if kind == "u":
                unique[table].append(tuple(own))
            else:
                foreign_keys[table].append(
                    ActualForeignKey(tuple(own), str(target), tuple(target_columns))
                )
        return ActualSchema(
            tuple(
                ActualTable(
                    name,
                    tuple(by_table[name]),
                    keys.get(name),
                    tuple(unique[name]),
                    tuple(foreign_keys[name]),
                )
                for name in names
            )
        )


class PsycopgJournalRecordsReader:
    """Реализация чтения журнала Liquibase."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def records(self, database: TargetDatabase) -> tuple[JournalRecord, ...]:
        with self._connector.connect(database) as connection:
            exists = connection.execute("SELECT to_regclass('public.databasechangelog')").fetchone()
            if exists is None or exists[0] is None:
                return ()
            rows = connection.execute(
                "SELECT id, author, filename, exectype FROM public.databasechangelog "
                "ORDER BY orderexecuted, dateexecuted"
            ).fetchall()
        return tuple(JournalRecord(str(i), str(a), str(f), str(e)) for i, a, f, e in rows)
