"""Каталоги дерева раскладки и файл реестра происхождения."""

import json
from pathlib import Path

#: Реестр происхождения — файл в корне дерева раскладки.
REGISTRY_RELPATH = "projects/layout-registry.json"


class SpaceStateError(Exception):
    """Целевой путь занят файлом: приведение к каталогу невозможно."""


class SpaceFileError(Exception):
    """Реестр происхождения не читается или не разбирается."""


class SpaceFS:
    """Каталоги и реестр рабочего пространства."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def ensure_directory(self, rel_path: str) -> bool:
        """Привести целевой путь к каталогу; True — создан, False — уже существовал."""
        target = self._root / rel_path
        if target.is_file():
            raise SpaceStateError(f"целевой путь занят файлом: {target}")
        existed = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        return not existed

    def load_registry(self) -> list[dict]:
        """Прочитать реестр происхождения; без файла — пустой перечень."""
        path = self._root / REGISTRY_RELPATH
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SpaceFileError(f"реестр происхождения не читается: {path}: {exc}") from exc
        if not isinstance(data, list):
            raise SpaceFileError(f"реестр происхождения не является массивом JSON: {path}")
        return data

    def save_registry(self, entries: list[dict]) -> None:
        """Записать реестр происхождения в корень дерева."""
        path = self._root / REGISTRY_RELPATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
