"""Загрузчик таксономии SPCF 2.0 из выгрузки taxonomy/ внутри утилиты."""

import json
from pathlib import Path

from classifier.domain.taxonomy import ID_PREFIXES, LEVELS, TaxonomyError, TaxonomyRecord

#: Обязательные поля записи уровня в выгрузке.
_REQUIRED_FIELDS = ("id", "code", "name", "name_ru", "description", "description_ru")


def load_taxonomy(export_dir: Path) -> dict[str, list[TaxonomyRecord]]:
    """Загрузить записи уровней L1–L4 из каталога выгрузки.

    Raises:
        TaxonomyError: каталог отсутствует, файл уровня не читается, запись не несёт
            обязательных полей или идентификатор не соответствует префиксу уровня.
    """
    if not export_dir.is_dir():
        raise TaxonomyError(f"каталог выгрузки отсутствует: {export_dir}")
    taxonomy: dict[str, list[TaxonomyRecord]] = {}
    for level, filename in LEVELS.items():
        taxonomy[level] = _load_level(export_dir / filename, level)
    return taxonomy


def _load_level(path: Path, level: str) -> list[TaxonomyRecord]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = raw["records"]
    except FileNotFoundError as exc:
        raise TaxonomyError(f"файл уровня отсутствует: {path}") from exc
    except (OSError, KeyError, ValueError) as exc:
        raise TaxonomyError(f"файл уровня не читается: {path}: {exc}") from exc

    prefix = ID_PREFIXES[level]
    loaded: list[TaxonomyRecord] = []
    for entry in records:
        missing = [f for f in _REQUIRED_FIELDS if not entry.get(f)]
        if missing:
            raise TaxonomyError(
                f"запись уровня {level} без обязательных полей {missing}: {entry.get('id')}"
            )
        record_id = entry["id"]
        if not record_id.startswith(f"{prefix}-"):
            raise TaxonomyError(
                f"идентификатор {record_id} не соответствует префиксу уровня {level} ({prefix}-)"
            )
        loaded.append(
            TaxonomyRecord(
                level=level,
                record_id=record_id,
                code=entry["code"],
                name=entry["name"],
                name_ru=entry["name_ru"],
                description=entry["description"],
                description_ru=entry["description_ru"],
            )
        )
    if not loaded:
        raise TaxonomyError(f"уровень {level} пуст: {path}")
    return loaded
