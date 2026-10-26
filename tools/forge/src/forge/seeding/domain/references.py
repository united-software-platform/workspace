"""Проверка ссылок внешних ключей между строками seed и циклов этих ссылок.

Сначала по таблицам и внешним ключам в порядке документа: цель вне seed, затем
неразрешённые ссылки по строкам. Затем циклы: граф «строка → строка цели FK» разбивается
на сильно связные компоненты; компонента больше одной строки — цикл. Ссылка строки на себя
ребром не считается: такую строку можно вставить одной командой.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Sequence

from forge.modeling.domain.foreign_key import ForeignKey
from forge.modeling.domain.violation import Violation
from forge.seeding.domain.checked_rows import CheckedRow, CheckedTable
from forge.seeding.domain.seed_value import SeedValue

Node = tuple[int, int]
"""Строка в графе ссылок: индекс таблицы среди проверенных и позиция строки в таблице."""


def reference_violations(
    tables: Sequence[CheckedTable], excluded: frozenset[str]
) -> list[Violation]:
    """Нарушения ссылок и циклов; `excluded` — таблицы seed, исключённые из-за структуры."""
    positions = {checked.table.name.value: index for index, checked in enumerate(tables)}
    seeded = frozenset(positions) | excluded
    violations: list[Violation] = []
    edges: dict[Node, list[Node]] = {}
    indexes: dict[tuple[int, ForeignKey], dict[tuple[SeedValue, ...], CheckedRow]] = {}
    for source, checked in enumerate(tables):
        checkable: list[tuple[ForeignKey, int]] = []
        for key in checked.table.foreign_keys:
            name = key.target.value
            if name not in seeded:
                violations.append(
                    Violation(
                        checked.name_path,
                        "unseeded_reference_table",
                        f"внешний ключ {key} ведёт на таблицу {name}, которой нет в seed: "
                        "справочник ссылается только на таблицы seed",
                    )
                )
            elif name in positions:
                checkable.append((key, positions[name]))
        for row in checked.rows:
            for key, target in checkable:
                values = row.key(key.columns)
                if values is None or any(value.is_null() for value in values):
                    continue
                if (target, key) not in indexes:
                    indexes[target, key] = _index(tables[target], key)
                hit = indexes[target, key].get(values)
                if hit is None:
                    pairs = ", ".join(
                        f"{column}={value}"
                        for column, value in zip(key.target_columns, values, strict=True)
                    )
                    violations.append(
                        Violation(
                            row.path,
                            "unresolved_reference",
                            f"внешний ключ {key}: в таблице {key.target} seed нет строки [{pairs}]",
                        )
                    )
                elif hit is not row:
                    edges.setdefault((source, row.position), []).append((target, hit.position))
    return violations + _cycle_violations(tables, edges)


def _index(target: CheckedTable, key: ForeignKey) -> dict[tuple[SeedValue, ...], CheckedRow]:
    """Первая строка цели по значениям колонок цели; строки с нарушенным значением или NULL
    в колонках цели не адресуемы."""
    index: dict[tuple[SeedValue, ...], CheckedRow] = {}
    for row in target.rows:
        values = row.key(key.target_columns)
        if values is not None and not any(value.is_null() for value in values):
            index.setdefault(values, row)
    return index


def _cycle_violations(
    tables: Sequence[CheckedTable], edges: dict[Node, list[Node]]
) -> list[Violation]:
    violations: list[Violation] = []
    cycles = [sorted(c) for c in _components(sorted(edges), edges) if len(c) > 1]
    for component in sorted(cycles):
        start = component[0]
        path = _cycle_path(start, frozenset(component), edges)
        labels = " → ".join(_label(tables, node) for node in path)
        violations.append(
            Violation(
                tables[start[0]].rows[start[1]].path,
                "reference_cycle",
                f"строки seed ссылаются друг на друга по кругу: {labels}; "
                "такие строки не вставить по одной",
            )
        )
    return violations


def _label(tables: Sequence[CheckedTable], node: Node) -> str:
    checked = tables[node[0]]
    return checked.rows[node[1]].label(checked.table)


def _components(nodes: Sequence[Node], edges: dict[Node, list[Node]]) -> list[list[Node]]:
    """Сильно связные компоненты алгоритмом Тарьяна без рекурсии: справочник может быть длинным."""
    order: dict[Node, int] = {}
    low: dict[Node, int] = {}
    stack: list[Node] = []
    on_stack: set[Node] = set()
    components: list[list[Node]] = []

    def visit(node: Node) -> Iterator[Node]:
        order[node] = low[node] = len(order)
        stack.append(node)
        on_stack.add(node)
        return iter(edges.get(node, ()))

    for root in nodes:
        if root in order:
            continue
        work = [(root, visit(root))]
        while work:
            node, successors = work[-1]
            for successor in successors:
                if successor not in order:
                    work.append((successor, visit(successor)))
                    break
                if successor in on_stack:
                    low[node] = min(low[node], order[successor])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == order[node]:
                    component: list[Node] = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    components.append(component)
    return components


def _cycle_path(start: Node, members: frozenset[Node], edges: dict[Node, list[Node]]) -> list[Node]:
    """Кратчайший цикл от `start` обратно к нему внутри компоненты: строки в порядке обхода."""
    previous: dict[Node, Node] = {}
    queue: deque[Node] = deque([start])
    while queue and start not in previous:
        node = queue.popleft()
        for successor in edges.get(node, ()):
            if successor in members and successor not in previous:
                previous[successor] = node
                queue.append(successor)
    chain: list[Node] = []
    node = previous[start]
    while node != start:
        chain.append(node)
        node = previous[node]
    return [start, *reversed(chain), start]
