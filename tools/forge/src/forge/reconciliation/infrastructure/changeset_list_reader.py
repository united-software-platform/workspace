"""Чтение `id`, автора и `logicalFilePath` changeset из changelog `forge generate`.

Сверка читает changelog своим разборщиком: от формата ей нужна только идентичность changeset,
а разборщик Миграции ей недоступен по карте контекстов.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge.reconciliation.application.contracts import ChangelogUnreadableError
from forge.reconciliation.domain.journal_check import ExpectedChangeSet


class YamlChangesetListReader:
    """Реализация контракта чтения changeset changelog попытки."""

    def read(self, path: str) -> tuple[ExpectedChangeSet, ...]:
        try:
            document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            raise ChangelogUnreadableError(f"changelog {path} не прочитать: {error}") from None
        try:
            return tuple(_changeset(entry) for entry in document["databaseChangeLog"] or [])
        except (KeyError, TypeError) as error:
            raise ChangelogUnreadableError(
                f"changelog {path} не в формате forge generate: {error!r}"
            ) from None


def _changeset(entry: Any) -> ExpectedChangeSet:
    changeset = entry["changeSet"]
    return ExpectedChangeSet(
        str(changeset["id"]), str(changeset["author"]), str(changeset["logicalFilePath"])
    )
