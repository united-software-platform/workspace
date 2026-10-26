"""Запись changelog данных в формате YAML Liquibase.

Каждое значение пишется типизированным литералом `valueComputed`: текст нормализованной формы
в кавычках с удвоенными кавычками внутри и приведение к типу колонки PostgreSQL — по той же
таблице отображения, что в changelog модели. NULL — явный `NULL`. Условия `where` собираются
из тех же литералов по всем колонкам первичного ключа.

Литералы и условия записываются строками YAML в двойных кавычках: так `NULL` не читается
как пустое значение YAML, а одинарные кавычки SQL не удваиваются ещё раз. Порядок ключей
задаёт код, поэтому повторная запись того же changelog даёт побайтово тот же файл.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge.migration.infrastructure.liquibase_changelog import AUTHOR, liquibase_type
from forge.modeling.domain.identifier import ColumnName
from forge.modeling.domain.table import Table
from forge.seeding.domain.data_changelog import DataChangelog, DataChangeSet
from forge.seeding.domain.row_changes import RowChange, RowInsert, RowUpdate
from forge.seeding.domain.seed import SeedRow
from forge.seeding.domain.seed_value import SeedValue


class _Sql(str):
    """Текст SQL в changelog: пишется строкой YAML в двойных кавычках."""


class _Dumper(yaml.SafeDumper):
    """Сериализатор changelog данных: `_Sql` — в двойных кавычках."""


_Dumper.add_representer(
    _Sql, lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
)


def literal(table: Table, column: ColumnName, value: SeedValue) -> str:
    """Литерал значения колонки: `'draft'::VARCHAR(32)`, `'true'::BOOLEAN` или `NULL`."""
    if value.is_null():
        return "NULL"
    text = str(value).replace("'", "''")
    return f"'{text}'::{liquibase_type(table.column(column).type)}"


def render_data_changelog(changelog: DataChangelog) -> str:
    """Текст changelog данных: заголовочный комментарий и YAML Liquibase."""
    document = {"databaseChangeLog": [_changeset(changelog, item) for item in changelog.changesets]}
    body = yaml.dump(
        document,
        Dumper=_Dumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    )
    header = (
        f"# Changelog данных операции {changelog.stamp}: "
        "построен forge generate-seed, вручную не правится\n"
    )
    return header + body


def _changeset(changelog: DataChangelog, item: DataChangeSet) -> dict[str, Any]:
    changes = item.group.changes
    return {
        "changeSet": {
            "id": item.id,
            "author": AUTHOR,
            "logicalFilePath": changelog.logical_file_path,
            "changes": [_forward(change) for change in changes],
            "rollback": [_backward(change) for change in reversed(changes)],
        }
    }


def _forward(change: RowChange) -> dict[str, Any]:
    if isinstance(change, RowInsert):
        return _insert(change.table, change.row)
    if isinstance(change, RowUpdate):
        return _update(change.table, change.after, change.changed())
    return _delete(change.table, change.row)


def _backward(change: RowChange) -> dict[str, Any]:
    """Действие отката строки: удалить вставленную, вернуть прежние значения, вставить удалённую."""
    if isinstance(change, RowInsert):
        return _delete(change.table, change.row)
    if isinstance(change, RowUpdate):
        return _update(change.table, change.before, change.changed())
    return _insert(change.table, change.row)


def _insert(table: Table, row: SeedRow) -> dict[str, Any]:
    return {
        "insert": {
            "tableName": table.name.value,
            "columns": [_column(table, column, value) for column, value in row.values],
        }
    }


def _update(table: Table, row: SeedRow, columns: tuple[ColumnName, ...]) -> dict[str, Any]:
    return {
        "update": {
            "tableName": table.name.value,
            "columns": [_column(table, column, row.value(column)) for column in columns],
            "where": _where(table, row),
        }
    }


def _delete(table: Table, row: SeedRow) -> dict[str, Any]:
    return {"delete": {"tableName": table.name.value, "where": _where(table, row)}}


def _column(table: Table, column: ColumnName, value: SeedValue) -> dict[str, Any]:
    return {"column": {"name": column.value, "valueComputed": _Sql(literal(table, column, value))}}


def _where(table: Table, row: SeedRow) -> _Sql:
    """Условие на все колонки первичного ключа в порядке ключа."""
    return _Sql(
        " AND ".join(
            f"{column.value} = {literal(table, column, row.value(column))}"
            for column in table.primary_key.columns
        )
    )


class LiquibaseYamlDataChangelogWriter:
    """Реализация контракта записи changelog данных."""

    def write(self, path: str, changelog: DataChangelog) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_data_changelog(changelog), encoding="utf-8")

    def remove(self, path: str) -> None:
        Path(path).unlink(missing_ok=True)
