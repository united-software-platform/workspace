"""Разница между принятым seed и seed попытки: изменения строк в порядке исполнения."""

from __future__ import annotations

import heapq
from collections.abc import Sequence

from forge.modeling.domain.foreign_key import ForeignKey
from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.table import Table
from forge.seeding.domain.row_changes import (
    RowChange,
    RowDelete,
    RowGroup,
    RowInsert,
    RowUpdate,
    UnsupportedRowChange,
    UnsupportedRowChangeError,
    row_label,
)
from forge.seeding.domain.seed import Seed, SeedRow, SeedTable
from forge.seeding.domain.seed_value import SeedValue

Node = tuple[int, int]
"""Строка seed: индекс таблицы в seed и позиция строки в таблице."""

Key = tuple[SeedValue, ...]


class SeedDiff:
    """Доменный сервис: изменения строк от принятого seed к seed попытки.

    Строки сопоставляются по первичному ключу, значения сравниваются в нормализованной форме:
    строка только в seed попытки — вставка, с тем же ключом и другими значениями — изменение,
    только в принятом seed — удаление. Таблица, убранная из seed, теряет все свои строки.
    Оба seed построены по одной модели.

    Порядок: вставки, затем изменения, затем удаления. Вставки идут от целевых строк внешних
    ключей к зависимым, удаления — от зависимых к целевым; при равенстве решает порядок таблиц
    и строк в seed: для удалений — в принятом, для вставок и изменений — в seed попытки.
    Соседние строки одной таблицы и одного вида собираются в группу — будущий changeset.

    Неисполнимые изменения собираются все и бросаются одним исключением:

    - новое значение набора `unique` совпадает с принятым значением другой изменяемой или
      удаляемой строки;
    - изменяемая строка меняет значение набора `unique`, на который ведёт внешний ключ, а на
      прежнее значение ссылается другая строка принятого seed либо новое занимает другая
      вставляемая или изменяемая строка. Ссылки по набору не следуют за его значением, поэтому
      ни один порядок такие изменения не исполнит.
    """

    def between(self, accepted: Seed, attempt: Seed) -> tuple[RowGroup, ...]:
        inserts: dict[Node, RowChange] = {}
        updates: dict[Node, RowChange] = {}
        deletes: dict[Node, RowChange] = {}
        for index, seed_table in enumerate(attempt.tables):
            before = _rows_by_key(accepted, seed_table.name)
            for position, row in enumerate(seed_table.rows):
                old = before.get(_key(seed_table, row))
                if old is None:
                    inserts[index, position] = RowInsert(seed_table.table, row)
                elif old != row:
                    updates[index, position] = RowUpdate(seed_table.table, old, row)
        for index, seed_table in enumerate(accepted.tables):
            after = _rows_by_key(attempt, seed_table.name)
            for position, row in enumerate(seed_table.rows):
                if _key(seed_table, row) not in after:
                    deletes[index, position] = RowDelete(seed_table.table, row)

        conflicts = _unique_conflicts([*inserts.values(), *updates.values()], updates, deletes)
        conflicts += _referenced_key_changes(
            accepted, [*inserts.values(), *updates.values()], updates
        )
        if conflicts:
            raise UnsupportedRowChangeError(conflicts)

        ordered = (
            _topological(attempt, inserts, dependents_first=False)
            + [updates[node] for node in sorted(updates)]
            + _topological(accepted, deletes, dependents_first=True)
        )
        return _groups(ordered)


def _key(seed_table: SeedTable, row: SeedRow) -> Key:
    return row.key(seed_table.table.primary_key.columns)


def _rows_by_key(seed: Seed, name: TableName) -> dict[Key, SeedRow]:
    if not seed.has_table(name):
        return {}
    seed_table = seed.table(name)
    return {_key(seed_table, row): row for row in seed_table.rows}


def _topological(
    seed: Seed, chosen: dict[Node, RowChange], dependents_first: bool
) -> list[RowChange]:
    """Строки `chosen` в порядке ссылок внешних ключей между ними.

    Ссылка строки на себя порядка не задаёт. Ссылки на строки вне `chosen` уже разрешены:
    целевая строка есть до вставок и остаётся до удалений. Граф ацикличен — циклы ссылок
    отклоняет фабрика seed.
    """
    waits: dict[Node, set[Node]] = {node: set() for node in chosen}
    for node in chosen:
        for target in _targets(seed, node):
            if target in chosen and target != node:
                if dependents_first:
                    waits[target].add(node)
                else:
                    waits[node].add(target)
    followers: dict[Node, list[Node]] = {node: [] for node in chosen}
    for node, prerequisites in waits.items():
        for prerequisite in prerequisites:
            followers[prerequisite].append(node)
    ready = [node for node, prerequisites in waits.items() if not prerequisites]
    heapq.heapify(ready)
    ordered: list[RowChange] = []
    while ready:
        node = heapq.heappop(ready)
        ordered.append(chosen[node])
        for follower in followers[node]:
            waits[follower].discard(node)
            if not waits[follower]:
                heapq.heappush(ready, follower)
    if len(ordered) != len(chosen):
        raise ValueError("строки seed ссылаются друг на друга по кругу")
    return ordered


def _targets(seed: Seed, node: Node) -> list[Node]:
    """Строки seed, на которые ссылается строка `node` своими внешними ключами."""
    seed_table = seed.tables[node[0]]
    row = seed_table.rows[node[1]]
    targets: list[Node] = []
    for key in seed_table.table.foreign_keys:
        values = row.key(key.columns)
        if any(value.is_null() for value in values) or not seed.has_table(key.target):
            continue
        index = next(i for i, t in enumerate(seed.tables) if t.name == key.target)
        position = _target_index(seed.tables[index], key).get(values)
        if position is not None:
            targets.append((index, position))
    return targets


def _target_index(target: SeedTable, key: ForeignKey) -> dict[Key, int]:
    index: dict[Key, int] = {}
    for position, row in enumerate(target.rows):
        index.setdefault(row.key(key.target_columns), position)
    return index


def _unique_conflicts(
    taking: Sequence[RowChange],
    updates: dict[Node, RowChange],
    deletes: dict[Node, RowChange],
) -> list[UnsupportedRowChange]:
    """Строки, чьё новое значение набора `unique` занято принятым значением другой строки,
    которая изменяется или удаляется; пара строк и набор называются один раз."""
    freeing = [*updates.values(), *deletes.values()]
    conflicts: list[UnsupportedRowChange] = []
    seen: set[tuple[str, frozenset[ColumnName], frozenset[str]]] = set()
    for change in taking:
        table = change.table
        row = _row(change)
        for unique in table.unique:
            new = row.key(unique.columns)
            if any(value.is_null() for value in new):
                continue
            for other in freeing:
                if other.table != table or other.key() == change.key():
                    continue
                old = other.before if isinstance(other, RowUpdate) else _row(other)
                if old.key(unique.columns) != new:
                    continue
                taker, giver = row_label(table, row), row_label(table, old)
                mark = (table.name.value, unique.composition(), frozenset((taker, giver)))
                if mark in seen:
                    continue
                seen.add(mark)
                conflicts.append(_conflict(change, other, unique.columns, taker, giver))
    return conflicts


def _referenced_key_changes(
    accepted: Seed, taking: Sequence[RowChange], updates: dict[Node, RowChange]
) -> list[UnsupportedRowChange]:
    """Изменения значения набора `unique`, на который ведёт внешний ключ, при ссылках на
    прежнее значение из принятого seed или на новое — из вставляемых и изменяемых строк.

    Ссылка строки на себя и значения с NULL не учитываются; ключи на PK не рассматриваются:
    смена PK — удаление и вставка. Пара строк и внешний ключ называются один раз.
    """
    conflicts: list[UnsupportedRowChange] = []
    seen: set[tuple[str, ForeignKey, frozenset[str]]] = set()
    for change in updates.values():
        assert isinstance(change, RowUpdate)
        table = change.table
        for source, key in _keys_to(accepted, taking, table.name):
            if frozenset(key.target_columns) == frozenset(table.primary_key.columns):
                continue
            old, new = change.before.key(key.target_columns), change.after.key(key.target_columns)
            if old == new:
                continue
            label = row_label(table, change.after)
            referencing = [
                row_label(source, row)
                for row in _rows_of(accepted, source.name)
                if _references(row, key, old)
            ] + [
                row_label(other.table, _row(other))
                for other in taking
                if other.table == source and _references(_row(other), key, new)
            ]
            for other_label in referencing:
                mark = (table.name.value, key, frozenset((label, other_label)))
                if other_label == label or mark in seen:
                    continue
                seen.add(mark)
                conflicts.append(_key_change(table, source, key, label, other_label))
    return conflicts


def _keys_to(
    accepted: Seed, taking: Sequence[RowChange], target: TableName
) -> list[tuple[Table, ForeignKey]]:
    """Внешние ключи таблиц обоих seed, ведущие на таблицу `target`, без повторов."""
    tables = [seed_table.table for seed_table in accepted.tables]
    tables += [change.table for change in taking if change.table not in tables]
    found: list[tuple[Table, ForeignKey]] = []
    for table in tables:
        for key in table.foreign_keys:
            if key.target == target and (table, key) not in found:
                found.append((table, key))
    return found


def _rows_of(seed: Seed, name: TableName) -> tuple[SeedRow, ...]:
    return seed.table(name).rows if seed.has_table(name) else ()


def _references(row: SeedRow, key: ForeignKey, values: Key) -> bool:
    own = row.key(key.columns)
    return not any(value.is_null() for value in own) and own == values


def _key_change(
    table: Table, source: Table, key: ForeignKey, label: str, other: str
) -> UnsupportedRowChange:
    listed = ", ".join(column.value for column in key.target_columns)
    return UnsupportedRowChange(
        "referenced_key_changed",
        table.name.value,
        tuple(column.value for column in key.target_columns),
        (label, other),
        f"строка {label} меняет значение [{listed}], на которое ведёт внешний ключ {key} "
        f"таблицы {source.name}, а строка {other} ссылается на прежнее или новое значение: "
        "ссылки по набору unique не исполнить ни в каком порядке; разнесите изменение "
        "значения и ссылок на него по двум операциям",
    )


def _row(change: RowChange) -> SeedRow:
    return change.after if isinstance(change, RowUpdate) else change.row


def _conflict(
    change: RowChange,
    other: RowChange,
    columns: tuple[ColumnName, ...],
    taker: str,
    giver: str,
) -> UnsupportedRowChange:
    listed = ", ".join(column.value for column in columns)
    action = "вставляется" if isinstance(change, RowInsert) else "изменяется"
    freed = "изменяется" if isinstance(other, RowUpdate) else "удаляется"
    return UnsupportedRowChange(
        "unique_conflict",
        change.table.name.value,
        tuple(column.value for column in columns),
        (taker, giver),
        f"строка {taker} {action} со значением набора unique [{listed}], которое занимает "
        f"строка {giver}, а она {freed}: изменения не выполнить ни в каком порядке; "
        "сначала освободите значение одной операцией, затем займите его другой",
    )


def _groups(ordered: list[RowChange]) -> tuple[RowGroup, ...]:
    groups: list[RowGroup] = []
    for change in ordered:
        last = groups[-1] if groups else None
        if last is not None and last.kind is change.kind and last.table == change.table:
            groups[-1] = RowGroup(last.kind, last.table, (*last.changes, change))
        else:
            groups.append(RowGroup(change.kind, change.table, (change,)))
    return tuple(groups)
