"""Чтение `reconcile.json` и `rollback.json` каталога попытки, удалений и строк changelog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from forge.operation.application.accepted_state import (
    DataChanges,
    DeletedRow,
    DestructiveChange,
    DiscrepancySummary,
    ReconcileSummary,
    RollbackSummary,
    TableRowCounts,
)

RECONCILE = "reconcile.json"
ROLLBACK = "rollback.json"


def _load(path: Path) -> dict[str, Any] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


class JsonAttemptResultsReader:
    """Реализация чтения результатов попытки; нечитаемый файл считается отсутствующим."""

    def reconcile(self, attempt_directory: str) -> ReconcileSummary | None:
        document = _load(Path(attempt_directory) / RECONCILE)
        if document is None:
            return None
        return ReconcileSummary(
            verdict=str(document.get("verdict")),
            discrepancies=tuple(
                DiscrepancySummary(
                    kind=str(item.get("kind")),
                    table=item.get("table"),
                    column=item.get("column"),
                    changeset=item.get("changeset"),
                    expected=str(item.get("expected")),
                    actual=str(item.get("actual")),
                    message=str(item.get("message")),
                )
                for item in document.get("discrepancies") or []
                if isinstance(item, dict)
            ),
        )

    def rollback(self, attempt_directory: str) -> RollbackSummary | None:
        document = _load(Path(attempt_directory) / ROLLBACK)
        if document is None:
            return None
        return RollbackSummary(
            action=str(document.get("action")),
            rolled_back=int(document.get("rolled_back") or 0),
            verified=document.get("verified") is True,
            fallback_reason=document.get("fallback_reason"),
        )

    def destructive(self, changelog: str) -> tuple[DestructiveChange, ...]:
        return destructive_changes(changelog)

    def data_changes(self, changelog: str) -> DataChanges:
        return _data_changes(changelog)


def destructive_changes(path: str) -> tuple[DestructiveChange, ...]:
    """Удаления changelog по блокам `changes`: только формы `dropTable` и `dropColumn`.

    Формат changelog знает запись контекста Миграция; здесь читаются только эти две формы,
    и тест сверяет их с выводом записи.
    """
    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        found: list[DestructiveChange] = []
        for entry in document["databaseChangeLog"] or []:
            for change in entry["changeSet"]["changes"]:
                if "dropTable" in change:
                    found.append(DestructiveChange(str(change["dropTable"]["tableName"]), None))
                elif "dropColumn" in change:
                    dropped = change["dropColumn"]
                    found.append(
                        DestructiveChange(str(dropped["tableName"]), str(dropped["columnName"]))
                    )
    except (OSError, UnicodeDecodeError, yaml.YAMLError, KeyError, TypeError):
        return ()
    return tuple(found)


_ACTIONS = {"insert": 0, "update": 1, "delete": 2}
_CONDITION = re.compile(r"(\w+) = (?:NULL|'((?:[^']|'')*)'::[^']+?)(?: AND |$)")


def _data_changes(path: str) -> DataChanges:
    """Строки changelog данных по блокам `changes`: формы `insert`, `update` и `delete`.

    Формат знает запись контекста Наполнение; здесь читаются только эти три формы и условие
    `where` по колонкам первичного ключа, а тест сверяет их с выводом записи.
    """
    counts: dict[str, list[int]] = {}
    deleted: list[DeletedRow] = []
    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for entry in document["databaseChangeLog"] or []:
            for change in entry["changeSet"]["changes"]:
                [(action, body)] = change.items()
                table = str(body["tableName"])
                counts.setdefault(table, [0, 0, 0])[_ACTIONS[action]] += 1
                if action == "delete":
                    deleted.append(DeletedRow(table, _key(str(body["where"]))))
    except (OSError, UnicodeDecodeError, yaml.YAMLError, KeyError, TypeError, ValueError):
        return DataChanges((), ())
    return DataChanges(
        tuple(TableRowCounts(table, *numbers) for table, numbers in counts.items()),
        tuple(deleted),
    )


def _key(where: str) -> tuple[tuple[str, str | None], ...]:
    """Первичный ключ из условия `where`: `code = 'archived'::VARCHAR(32)` → `code`, `archived`."""
    pairs: list[tuple[str, str | None]] = []
    position = 0
    while position < len(where):
        found = _CONDITION.match(where, position)
        if found is None or found.end() == position:
            raise ValueError(f"условие {where!r} не по первичному ключу")
        text = found.group(2)
        pairs.append((found.group(1), None if text is None else text.replace("''", "'")))
        position = found.end()
    if not pairs:
        raise ValueError("пустое условие where")
    return tuple(pairs)
