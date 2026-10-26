"""Запись changelog в формате YAML Liquibase и обратное чтение его сводки.

Отображение типов модели в типы Liquibase для PostgreSQL живёт здесь: это знание о Liquibase
и СУБД, а не о формате модели. Порядок ключей задаёт код, поэтому повторная запись того же
changelog даёт побайтово тот же файл.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from forge.migration.application.changelog_storage import (
    ChangelogSummary,
    ChangelogUnreadableError,
    ConstraintRef,
    RowRef,
)
from forge.migration.domain.changelog import Changelog, ChangeSet
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
)
from forge.modeling.domain.column import Column
from forge.modeling.domain.column_type import ColumnType, TypeKind
from forge.modeling.domain.foreign_key import ForeignKey
from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.table import Table
from forge.modeling.domain.unique_set import UniqueSet

AUTHOR = "forge"

# Предел идентификатора PostgreSQL — 63 символа: префикс `fk_`/`uq_`, таблица, `_` и hash8
_CONSTRAINT_TABLE_LENGTH = 51
_HASH_LENGTH = 8

_TYPES: dict[TypeKind, str] = {
    TypeKind.INTEGER: "INTEGER",
    TypeKind.BIGINT: "BIGINT",
    TypeKind.BOOLEAN: "BOOLEAN",
    TypeKind.TEXT: "TEXT",
    TypeKind.DATE: "DATE",
    TypeKind.TIMESTAMP: "TIMESTAMP WITHOUT TIME ZONE",
    TypeKind.TIMESTAMP_TZ: "TIMESTAMP WITH TIME ZONE",
    TypeKind.UUID: "UUID",
}


def liquibase_type(column_type: ColumnType) -> str:
    """Тип Liquibase для PostgreSQL по типу колонки модели."""
    if column_type.kind is TypeKind.STRING:
        return f"VARCHAR({column_type.length})"
    if column_type.kind is TypeKind.DECIMAL:
        return f"NUMERIC({column_type.precision}, {column_type.scale})"
    return _TYPES[column_type.kind]


def primary_key_name(table: str) -> str:
    """Имя ограничения первичного ключа таблицы."""
    return f"pk_{table}"


def unique_name(table: TableName, unique: UniqueSet) -> str:
    """Имя ограничения уникальности: `uq_<таблица>_<hash8>`.

    Хеш берётся от таблицы и отсортированных колонок набора, поэтому порядок колонок и место
    набора в модели на имя не влияют.
    """
    columns = ",".join(sorted(column.value for column in unique.columns))
    return _constraint_name("uq", table, f"{table}|{columns}")


def foreign_key_name(table: TableName, key: ForeignKey) -> str:
    """Имя ограничения внешнего ключа: `fk_<таблица>_<hash8>`.

    Хеш берётся от таблицы, пар «колонка FK → колонка цели», отсортированных по колонке FK,
    и целевой таблицы: перестановка пар и место ключа в модели на имя не влияют.
    """
    pairs = ",".join(
        f"{own}>{other}" for own, other in sorted((a.value, b.value) for a, b in key.pairs())
    )
    return _constraint_name("fk", table, f"{table}|{pairs}|{key.target}")


def _constraint_name(prefix: str, table: TableName, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:_HASH_LENGTH]
    return f"{prefix}_{table.value[:_CONSTRAINT_TABLE_LENGTH]}_{digest}"


class LiquibaseConstraintNaming:
    """Реализация контракта имён ограничений, общая с записью changelog."""

    def unique(self, table: TableName, unique: UniqueSet) -> str:
        return unique_name(table, unique)

    def foreign_key(self, table: TableName, key: ForeignKey) -> str:
        return foreign_key_name(table, key)


def render_changelog(changelog: Changelog) -> str:
    """Текст changelog: заголовочный комментарий и YAML Liquibase."""
    document = {"databaseChangeLog": [_changeset(changelog, item) for item in changelog.changesets]}
    body = yaml.safe_dump(
        document, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000
    )
    header = (
        f"# Changelog операции {changelog.stamp}: построен forge generate, вручную не правится\n"
    )
    return header + body


def _changeset(changelog: Changelog, item: ChangeSet) -> dict[str, Any]:
    changeset: dict[str, Any] = {
        "id": item.id,
        "author": AUTHOR,
        "logicalFilePath": changelog.logical_file_path,
        "changes": _forward(item.change),
    }
    # Откат создания Liquibase выводит сам; откат удаления задаётся явно по принятой модели
    if isinstance(item.change, DropTable | DropColumn | DropUnique | DropForeignKey):
        changeset["rollback"] = _restore(item.change)
    return {"changeSet": changeset}


def _forward(change: SchemaChange) -> list[dict[str, Any]]:
    if isinstance(change, CreateTable):
        return _create_table(change.table)
    if isinstance(change, AddColumn):
        return _add_column(change.table, change.column, change.nullable)
    if isinstance(change, AddUnique):
        return [_add_unique(change.table, change.unique)]
    if isinstance(change, AddForeignKey):
        return [_add_foreign_key(change.table, change.key)]
    if isinstance(change, DropTable):
        return [{"dropTable": {"tableName": change.table.name.value}}]
    if isinstance(change, DropUnique):
        return [
            {
                "dropUniqueConstraint": {
                    "tableName": change.table.value,
                    "constraintName": unique_name(change.table, change.unique),
                }
            }
        ]
    if isinstance(change, DropForeignKey):
        return [
            {
                "dropForeignKeyConstraint": {
                    "baseTableName": change.table.value,
                    "constraintName": foreign_key_name(change.table, change.key),
                }
            }
        ]
    return [
        {
            "dropColumn": {
                "tableName": change.table.value,
                "columnName": change.column.name.value,
            }
        }
    ]


def _restore(change: DropTable | DropColumn | DropUnique | DropForeignKey) -> list[dict[str, Any]]:
    """Откат удаления: структура объекта по принятой модели, данные не восстанавливаются.

    Откат удаления таблицы восстанавливает и её наборы уникальности; внешние ключи
    восстанавливает откат их собственных changeset.
    """
    if isinstance(change, DropTable):
        table = change.table
        return _create_table(table) + [_add_unique(table.name, unique) for unique in table.unique]
    if isinstance(change, DropUnique):
        return [_add_unique(change.table, change.unique)]
    if isinstance(change, DropForeignKey):
        return [_add_foreign_key(change.table, change.key)]
    return _add_column(change.table, change.column, change.nullable)


def _add_unique(table: TableName, unique: UniqueSet) -> dict[str, Any]:
    return {
        "addUniqueConstraint": {
            "tableName": table.value,
            "columnNames": _names(unique.columns),
            "constraintName": unique_name(table, unique),
        }
    }


def _add_foreign_key(table: TableName, key: ForeignKey) -> dict[str, Any]:
    return {
        "addForeignKeyConstraint": {
            "baseTableName": table.value,
            "baseColumnNames": _names(key.columns),
            "referencedTableName": key.target.value,
            "referencedColumnNames": _names(key.target_columns),
            "constraintName": foreign_key_name(table, key),
        }
    }


def _names(columns: tuple[ColumnName, ...]) -> str:
    return ", ".join(column.value for column in columns)


def _create_table(table: Table) -> list[dict[str, Any]]:
    name = table.name.value
    columns = [_column(column, table.is_nullable(column.name)) for column in table.columns]
    return [
        {"createTable": {"tableName": name, "columns": columns}},
        {
            "addPrimaryKey": {
                "tableName": name,
                "columnNames": _names(table.primary_key.columns),
                "constraintName": primary_key_name(name),
            }
        },
    ]


def _add_column(table: TableName, column: Column, nullable: bool) -> list[dict[str, Any]]:
    return [
        {
            "addColumn": {
                "tableName": table.value,
                "columns": [_column(column, nullable)],
            }
        }
    ]


def _column(column: Column, nullable: bool) -> dict[str, Any]:
    definition: dict[str, Any] = {"name": column.name.value, "type": liquibase_type(column.type)}
    if not nullable:
        definition["constraints"] = {"nullable": False}
    return {"column": definition}


class LiquibaseYamlChangelogWriter:
    """Реализация контракта записи changelog."""

    def write(self, path: str, changelog: Changelog) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_changelog(changelog), encoding="utf-8")

    def remove(self, path: str) -> None:
        Path(path).unlink(missing_ok=True)


class LiquibaseYamlChangelogReader:
    """Реализация контракта чтения сводки changelog, построенного `forge generate`."""

    def exists(self, path: str) -> bool:
        return Path(path).is_file()

    def read(self, path: str) -> ChangelogSummary:
        try:
            document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            raise ChangelogUnreadableError(f"changelog {path} не прочитать: {error}") from None
        try:
            return _summary(document)
        except (KeyError, TypeError, AttributeError) as error:
            raise ChangelogUnreadableError(
                f"changelog {path} не в формате forge generate: {error!r}"
            ) from None


# Действия changelog данных `forge generate-seed`
_DATA_ACTIONS = frozenset({"insert", "update", "delete"})


def _summary(document: Any) -> ChangelogSummary:
    """Сводка по блокам `changes`; блоки `rollback` изменений схемы в неё не входят.

    У changeset данных из блока `rollback` берутся условия и прежние значения строк: см. `_rows`.
    """
    ids: list[str] = []
    tables: list[str] = []
    columns: list[tuple[str, str]] = []
    dropped_tables: list[str] = []
    dropped_columns: list[tuple[str, str]] = []
    constraints: list[ConstraintRef] = []
    dropped_constraints: list[ConstraintRef] = []
    rows: dict[str, list[RowRef]] = {action: [] for action in _DATA_ACTIONS}
    paths: set[str] = set()
    for entry in document["databaseChangeLog"] or []:
        changeset = entry["changeSet"]
        ids.append(str(changeset["id"]))
        paths.add(str(changeset["logicalFilePath"]))
        for action, row in _rows(changeset):
            rows[action].append(row)
        for change in changeset["changes"]:
            if "createTable" in change:
                tables.append(str(change["createTable"]["tableName"]))
            elif "addColumn" in change:
                table = str(change["addColumn"]["tableName"])
                columns += [
                    (table, str(c["column"]["name"])) for c in change["addColumn"]["columns"]
                ]
            elif "dropTable" in change:
                dropped_tables.append(str(change["dropTable"]["tableName"]))
            elif "dropColumn" in change:
                dropped = change["dropColumn"]
                dropped_columns.append((str(dropped["tableName"]), str(dropped["columnName"])))
            elif "addUniqueConstraint" in change:
                constraints.append(
                    _constraint("unique", change["addUniqueConstraint"], "tableName")
                )
            elif "addForeignKeyConstraint" in change:
                body = change["addForeignKeyConstraint"]
                constraints.append(_constraint("foreign_key", body, "baseTableName"))
            elif "dropUniqueConstraint" in change:
                body = change["dropUniqueConstraint"]
                dropped_constraints.append(_constraint("unique", body, "tableName"))
            elif "dropForeignKeyConstraint" in change:
                body = change["dropForeignKeyConstraint"]
                dropped_constraints.append(_constraint("foreign_key", body, "baseTableName"))
    if len(paths) > 1:
        raise TypeError(f"у changeset разные logicalFilePath: {sorted(paths)}")
    return ChangelogSummary(
        logical_file_path=paths.pop() if paths else None,
        changeset_ids=tuple(ids),
        tables=tuple(tables),
        columns=tuple(columns),
        dropped_tables=tuple(dropped_tables),
        dropped_columns=tuple(dropped_columns),
        constraints=tuple(constraints),
        dropped_constraints=tuple(dropped_constraints),
        inserted_rows=tuple(rows["insert"]),
        updated_rows=tuple(rows["update"]),
        deleted_rows=tuple(rows["delete"]),
    )


def _rows(changeset: Any) -> list[tuple[str, RowRef]]:
    """Строки changeset данных: действие и строка с условием и литералами из отката.

    Откат строит `forge generate-seed` в обратном порядке, по действию на строку: вставке
    отвечает удаление с условием на ключ, изменению — изменение к прежним значениям,
    удалению — вставка всех прежних значений.
    """
    forward = [change for change in changeset["changes"] if _DATA_ACTIONS & change.keys()]
    if not forward:
        return []
    backward = list(reversed(changeset["rollback"]))
    if len(backward) != len(forward):
        raise TypeError(f"у changeset {changeset['id']} откат не по действию на строку")
    found: list[tuple[str, RowRef]] = []
    for change, restore in zip(forward, backward, strict=True):
        if "insert" in change:
            body = restore["delete"]
            found.append(("insert", RowRef(str(body["tableName"]), str(body["where"]))))
        elif "update" in change:
            body = restore["update"]
            row = RowRef(str(body["tableName"]), str(body["where"]), _literals(body))
            found.append(("update", row))
        else:
            where = str(change["delete"]["where"])
            body = restore["insert"]
            found.append(("delete", RowRef(str(body["tableName"]), where, _literals(body))))
    return found


def _literals(body: Any) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(c["column"]["name"]), str(c["column"]["valueComputed"])) for c in body["columns"]
    )


def _constraint(kind: str, body: Any, table_key: str) -> ConstraintRef:
    return ConstraintRef(kind, str(body[table_key]), str(body["constraintName"]))
