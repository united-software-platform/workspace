"""Слаги уровней L1/L2 из выгрузки таксономии классификатора."""

import json
from pathlib import Path


class TaxonomyFileError(Exception):
    """Выгрузка таксономии не найдена, не читается или не разбирается."""


class TaxonomyLookupError(Exception):
    """Запись уровня отсутствует в выгрузке либо не несёт слага code."""


class TaxonomyCodes:
    """Читает слаг уровня по идентификатору записи выгрузки."""

    def __init__(self, taxonomy_dir: Path) -> None:
        self._dir = Path(taxonomy_dir)

    def slug_l1(self, record_id: str) -> str:
        """Слаг записи уровня L1."""
        return self._slug("l1_application_domains.json", "L1", record_id)

    def slug_l2(self, record_id: str) -> str:
        """Слаг записи уровня L2."""
        return self._slug("l2_activity_subdomains.json", "L2", record_id)

    def _slug(self, filename: str, level: str, record_id: str) -> str:
        path = self._dir / filename
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise TaxonomyFileError(f"выгрузка таксономии не читается: {path}") from exc
        except json.JSONDecodeError as exc:
            raise TaxonomyFileError(f"выгрузка таксономии не разбирается: {path}: {exc}") from exc
        records = data.get("records") if isinstance(data, dict) else None
        if not isinstance(records, list):
            raise TaxonomyFileError(f"выгрузка таксономии не несёт перечня записей: {path}")
        for record in records:
            if isinstance(record, dict) and record.get("id") == record_id:
                code = record.get("code")
                if not code:
                    raise TaxonomyLookupError(
                        f"запись таксономии {record_id} уровня {level} не несёт слага code"
                    )
                return str(code)
        raise TaxonomyLookupError(
            f"запись таксономии {record_id} уровня {level} отсутствует в выгрузке"
        )
