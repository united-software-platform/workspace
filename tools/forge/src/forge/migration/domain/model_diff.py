"""Разница между принятой моделью и моделью попытки."""

from __future__ import annotations

from forge.migration.domain.changes import (
    AddColumn,
    AddForeignKey,
    AddUnique,
    CreateTable,
    DropColumn,
    DropForeignKey,
    DropTable,
    DropUnique,
    SchemaChange,
    UnsupportedChange,
    UnsupportedChangeError,
)
from forge.modeling.domain.data_model import DataModel
from forge.modeling.domain.table import Table


class ModelDiff:
    """Доменный сервис: изменения схемы от принятой модели к модели попытки.

    Разрешены новая и удалённая таблица, новая и удалённая колонка существующей таблицы,
    новый и удалённый набор уникальности и внешний ключ. Удаление колонки первичного ключа
    не даёт `DropColumn`: смена ключа уже отклоняется. Смена типа, итоговой допустимости NULL
    и первичного ключа — неподдерживаемые изменения; они собираются все и бросаются одним
    исключением. Переименование неотличимо от удаления и добавления и выражается ими.

    Ограничения отождествляются по содержимому: набор — по составу колонок, внешний ключ —
    по целевой таблице и парам колонок; изменение ограничения — удаление и добавление.
    Внешние ключи удаляемой таблицы и ключи на неё удаляются отдельно, а наборы удаляемой
    таблицы — нет: их снимает удаление таблицы и восстанавливает его откат.

    Порядок групп: удаление внешних ключей, удаление наборов, удаление таблиц, удаление
    колонок, создание таблиц, добавление колонок, добавление наборов, добавление внешних
    ключей. Удаления идут в порядке принятой модели, добавления — модели попытки.
    """

    def between(self, accepted: DataModel, attempt: DataModel) -> tuple[SchemaChange, ...]:
        unsupported: list[UnsupportedChange] = []
        for table in accepted.tables:
            if attempt.has_table(table.name):
                unsupported += _table_changes(table, attempt.table(table.name))
        if unsupported:
            raise UnsupportedChangeError(unsupported)

        changes: list[SchemaChange] = []
        for table in accepted.tables:
            kept = attempt.table(table.name).foreign_keys if attempt.has_table(table.name) else ()
            changes += [
                DropForeignKey(table.name, key) for key in table.foreign_keys if key not in kept
            ]
        for table in accepted.tables:
            if attempt.has_table(table.name):
                kept_sets = attempt.table(table.name).unique
                changes += [
                    DropUnique(table.name, unique)
                    for unique in table.unique
                    if unique not in kept_sets
                ]
        changes += [
            DropTable(table) for table in accepted.tables if not attempt.has_table(table.name)
        ]
        for table in accepted.tables:
            if attempt.has_table(table.name):
                changes += _dropped_columns(table, attempt.table(table.name))
        changes += [
            CreateTable(table) for table in attempt.tables if not accepted.has_table(table.name)
        ]
        for table in attempt.tables:
            if accepted.has_table(table.name):
                known = {column.name for column in accepted.table(table.name).columns}
                changes += [
                    AddColumn(table.name, column, table.is_nullable(column.name))
                    for column in table.columns
                    if column.name not in known
                ]
        for table in attempt.tables:
            before = accepted.table(table.name).unique if accepted.has_table(table.name) else ()
            changes += [
                AddUnique(table.name, unique) for unique in table.unique if unique not in before
            ]
        for table in attempt.tables:
            known_keys = (
                accepted.table(table.name).foreign_keys if accepted.has_table(table.name) else ()
            )
            changes += [
                AddForeignKey(table.name, key)
                for key in table.foreign_keys
                if key not in known_keys
            ]
        return tuple(changes)


def _dropped_columns(accepted: Table, attempt: Table) -> list[SchemaChange]:
    names = {column.name for column in attempt.columns}
    return [
        DropColumn(accepted.name, column, accepted.is_nullable(column.name))
        for column in accepted.columns
        if column.name not in names and column.name not in accepted.primary_key
    ]


def _table_changes(accepted: Table, attempt: Table) -> list[UnsupportedChange]:
    table = accepted.name.value
    names = {column.name for column in attempt.columns}
    rejected: list[UnsupportedChange] = []
    for column in accepted.columns:
        if column.name not in names:
            continue
        name = column.name.value
        changed = attempt.column(column.name)
        if changed.type != column.type:
            rejected.append(
                UnsupportedChange(
                    "column_type_changed",
                    table,
                    name,
                    f"тип колонки {table}.{name} изменён: {column.type} → {changed.type}",
                )
            )
        before, after = accepted.is_nullable(column.name), attempt.is_nullable(column.name)
        if before != after:
            rejected.append(
                UnsupportedChange(
                    "column_nullable_changed",
                    table,
                    name,
                    f"допустимость NULL колонки {table}.{name} изменена: "
                    f"{_nullable(before)} → {_nullable(after)}",
                )
            )
    if accepted.primary_key != attempt.primary_key:
        rejected.append(
            UnsupportedChange(
                "primary_key_changed",
                table,
                None,
                f"первичный ключ таблицы {table} изменён: {_key(accepted)} → {_key(attempt)}",
            )
        )
    return rejected


def _nullable(nullable: bool) -> str:
    return "NULL" if nullable else "NOT NULL"


def _key(table: Table) -> str:
    return "[" + ", ".join(column.value for column in table.primary_key.columns) + "]"
