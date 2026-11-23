"""Чтение контрактов прогона classify из каталога беклога."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: Принятость прогона: строка confirmed с истинным accepted во фронтматтере.
_ACCEPTED_PATTERN = re.compile(r"(?m)^confirmed:\s*\n\s+accepted:\s*true\s*$")


class RunFileError(Exception):
    """Файл прогона не найден, не читается или не разбирается."""


@dataclass(frozen=True)
class RunContracts:
    """Контракты прогона: карточка проекта и итог классификации."""

    card: dict
    classification: dict


class RunReader:
    """Читает card.json, classification.json и признак принятия прогона."""

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = Path(run_dir)

    def read(self) -> RunContracts:
        """Прочитать контракты прогона."""
        card = self._load("card.json")
        classification = self._load("classification.json")
        return RunContracts(card=card, classification=classification)

    def accepted(self) -> bool:
        """Прочитать признак принятия классификации из беклога прогона."""
        tasks = self._run_dir / "tasks.md"
        try:
            text = tasks.read_text(encoding="utf-8")
        except OSError as exc:
            raise RunFileError(f"беклог прогона не читается: {tasks}") from exc
        closing = text.find("\n---", 3)
        frontmatter = text[: closing if closing != -1 else len(text)]
        return bool(_ACCEPTED_PATTERN.search(frontmatter))

    def _load(self, filename: str) -> dict:
        path = self._run_dir / filename
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RunFileError(f"файл прогона не найден или не читается: {path}") from exc
        except json.JSONDecodeError as exc:
            raise RunFileError(f"файл прогона не разбирается: {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise RunFileError(f"файл прогона не является объектом JSON: {path}")
        return data
