"""Принятое состояние проекта в его корне: модель, seed, changelog операций и `master.yaml`."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from forge.operation.application.accepted_state import AcceptanceError, AcceptedFiles
from forge.operation.infrastructure.attempt_results import destructive_changes

MODEL = "model.yaml"
SEED = "seed.yaml"
CHANGELOG = "changelog.yaml"
MASTER = "master.yaml"


class FileAcceptedState:
    """Реализация принятого состояния: файлы в корне принятого состояния (`FORGE_ACCEPTED_DIR`).

    `include` в `master.yaml` указывает файл относительно самого `master.yaml`: так Liquibase
    находит его при любом каталоге поиска, а `logicalFilePath` changeset уже задан в файле.
    `master.yaml` общий для операций модели и seed: порядок `include` равен порядку принятия.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def files(self, stamp: str) -> AcceptedFiles:
        changelog = self._root / "changelog"
        return AcceptedFiles(
            model=(self._root / MODEL).as_posix(),
            changelog=(changelog / f"{stamp}.yaml").as_posix(),
            master=(changelog / MASTER).as_posix(),
        )

    def seed_files(self, stamp: str) -> AcceptedFiles:
        files = self.files(stamp)
        return AcceptedFiles(
            model=None,
            changelog=files.changelog,
            master=files.master,
            seed=(self._root / SEED).as_posix(),
        )

    def accept(self, stamp: str, attempt_directory: str) -> AcceptedFiles:
        """Принять модель; удалённые ею колонки снять из строк принятого seed той же правкой.

        `seed` в ответе — только если принятый seed изменён.
        """
        files = self.files(stamp)
        self._copy(stamp, attempt_directory, MODEL, str(files.model))
        dropped = {
            (change.table, change.column)
            for change in destructive_changes(files.changelog)
            if change.column is not None
        }
        seed = self._root / SEED
        if dropped and seed.is_file() and _drop_seed_columns(seed, dropped):
            return AcceptedFiles(files.model, files.changelog, files.master, seed.as_posix())
        return files

    def accept_seed(self, stamp: str, attempt_directory: str) -> AcceptedFiles:
        files = self.seed_files(stamp)
        self._copy(stamp, attempt_directory, SEED, str(files.seed))
        return files

    def _copy(self, stamp: str, attempt_directory: str, name: str, target: str) -> None:
        """Главный файл попытки и её changelog — в корень, `include` — в `master.yaml`."""
        files = self.files(stamp)
        source = Path(attempt_directory)
        for required in (name, CHANGELOG):
            if not (source / required).is_file():
                raise AcceptanceError(f"в каталоге попытки {attempt_directory} нет {required}")
        try:
            Path(files.changelog).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
            shutil.copyfile(source / CHANGELOG, files.changelog)
            self._include(Path(files.master), f"{stamp}.yaml")
        except OSError as error:
            raise AcceptanceError(f"принять в {self._root} не удалось: {error}") from None

    @staticmethod
    def _include(master: Path, file: str) -> None:
        document: dict[str, Any] = {"databaseChangeLog": []}
        if master.is_file():
            loaded = yaml.safe_load(master.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict) or not isinstance(
                loaded.get("databaseChangeLog") or [], list
            ):
                raise AcceptanceError(f"{master} не в формате master-changelog")
            document = {"databaseChangeLog": loaded.get("databaseChangeLog") or []}
        entries: list[Any] = document["databaseChangeLog"]
        if any(isinstance(e, dict) and e.get("include", {}).get("file") == file for e in entries):
            return
        entries.append({"include": {"file": file, "relativeToChangelogFile": True}})
        header = "# Принятые changelog операций по порядку принятия: ведёт forge close\n"
        body = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
        draft = master.with_name(master.name + ".tmp")
        draft.write_text(header + body, encoding="utf-8")
        os.replace(draft, master)


def _drop_seed_columns(seed: Path, dropped: set[tuple[str, str]]) -> bool:
    """Убрать из строк seed ключи удалённых колонок; `True` — файл изменён.

    Правится дерево узлов YAML, а не загруженные значения: стиль и текст каждого скаляра
    остаются как в файле, поэтому значения остальных колонок не меняют вид и тип.
    """
    try:
        root = yaml.compose(seed.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise AcceptanceError(f"принятый seed {seed} не прочитать: {error}") from None
    changed = False
    for table in _children(_field(root, "tables")):
        name = _field(table, "name")
        if not isinstance(name, ScalarNode):
            continue
        columns = {column for t, column in dropped if t == name.value}
        for row in _children(_field(table, "rows")):
            if not isinstance(row, MappingNode) or not columns:
                continue
            kept = [
                (k, v)
                for k, v in row.value
                if not (isinstance(k, ScalarNode) and k.value in columns)
            ]
            changed = changed or len(kept) != len(row.value)
            row.value = kept
    if not changed:
        return False
    text = yaml.serialize(root, allow_unicode=True, width=1000)
    draft = seed.with_name(seed.name + ".tmp")
    try:
        draft.write_text(text, encoding="utf-8")
        os.replace(draft, seed)
    except OSError as error:
        raise AcceptanceError(f"принятый seed {seed} не записать: {error}") from None
    return True


def _field(node: Node | None, key: str) -> Node | None:
    if not isinstance(node, MappingNode):
        return None
    return next((v for k, v in node.value if isinstance(k, ScalarNode) and k.value == key), None)


def _children(node: Node | None) -> list[Node]:
    return list(node.value) if isinstance(node, SequenceNode) else []
