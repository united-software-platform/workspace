"""Тесты загрузчика таксономии: нормальная загрузка и ошибки неполной выгрузки."""

import json
from pathlib import Path

import pytest

from classifier.domain.taxonomy import LEVELS, TaxonomyError
from classifier.infrastructure.taxonomy_loader import load_taxonomy

EXPORT_DIR = Path(__file__).resolve().parents[1] / "taxonomy"
EXPECTED_COUNTS = {
    "L1_application_domain": 16,
    "L2_activity_subdomain": 37,
    "L3_problem_domain": 27,
    "L4_solution_archetype": 35,
}


def test_load_real_export() -> None:
    taxonomy = load_taxonomy(EXPORT_DIR)
    assert set(taxonomy) == set(LEVELS)
    for level, count in EXPECTED_COUNTS.items():
        assert len(taxonomy[level]) == count, level
    record = taxonomy["L1_application_domain"][0]
    assert record.record_id.startswith("DOM-")
    assert " | " in record.text() and record.name_ru in record.text()


def test_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(TaxonomyError, match="каталог выгрузки отсутствует"):
        load_taxonomy(tmp_path / "нет-такого")


def _make_export(tmp_path: Path) -> Path:
    export = tmp_path / "export"
    export.mkdir()
    prefixes = {
        "l1_application_domains.json": "DOM",
        "l2_activity_subdomains.json": "SUB",
        "l3_problem_domains.json": "PRB",
        "l4_solution_archetypes.json": "SOL",
    }
    for filename, prefix in prefixes.items():
        sample = {
            "id": f"{prefix}-001",
            "code": "test",
            "name": "Test",
            "name_ru": "Тест",
            "description": "Desc",
            "description_ru": "Описание",
        }
        (export / filename).write_text(
            json.dumps({"records": [sample]}, ensure_ascii=False), encoding="utf-8"
        )
    return export


def test_incomplete_record_raises(tmp_path: Path) -> None:
    export = _make_export(tmp_path)
    path = export / "l1_application_domains.json"
    data = json.loads(path.read_text())
    del data["records"][0]["name_ru"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(TaxonomyError, match="обязательных полей"):
        load_taxonomy(export)


def test_wrong_prefix_raises(tmp_path: Path) -> None:
    export = _make_export(tmp_path)
    path = export / "l2_activity_subdomains.json"
    data = json.loads(path.read_text())
    data["records"][0]["id"] = "DOM-999"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(TaxonomyError, match="префиксу"):
        load_taxonomy(export)


def test_missing_level_file_raises(tmp_path: Path) -> None:
    export = _make_export(tmp_path)
    (export / "l3_problem_domains.json").unlink()
    with pytest.raises(TaxonomyError, match="файл уровня отсутствует"):
        load_taxonomy(export)
