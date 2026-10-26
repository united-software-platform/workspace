"""Запись файла результата команды в JSON."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class JsonResultWriter:
    """Реализация контракта записи результата: файл пишется целиком и атомарно."""

    def write(self, path: str, document: Mapping[str, Any]) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        draft = target.with_name(target.name + ".tmp")
        draft.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(draft, target)
