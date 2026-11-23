"""Фики прогона classify и выгрузки таксономии для тестов раскладки."""

import json
from pathlib import Path


def make_taxonomy(taxonomy_dir: Path) -> Path:
    """Выгрузка таксономии с записями уровней, несущими слаги code."""
    taxonomy_dir.mkdir(parents=True, exist_ok=True)
    (taxonomy_dir / "l1_application_domains.json").write_text(
        json.dumps(
            {
                "records": [
                    {"id": "DOM-008", "code": "software-engineering"},
                    {"id": "DOM-010", "code": "data-engineering"},
                    {"id": "DOM-011"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (taxonomy_dir / "l2_activity_subdomains.json").write_text(
        json.dumps(
            {
                "records": [
                    {"id": "SUB-018", "code": "data-modeling"},
                    {"id": "SUB-023", "code": "ai-agent-engineering"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return taxonomy_dir


def make_run(
    run_dir: Path,
    *,
    name: str = "forge",
    organization: str | None = "usp",
    l1: str = "DOM-010",
    l2: str = "SUB-018",
    accepted: bool = True,
) -> Path:
    """Каталог прогона classify с карточкой, итогом и беклогом принятия."""
    run_dir.mkdir(parents=True, exist_ok=True)
    card: dict = {"name": name}
    if organization is not None:
        card["facets"] = {"organization": organization}
    (run_dir / "card.json").write_text(json.dumps(card), encoding="utf-8")
    (run_dir / "classification.json").write_text(
        json.dumps(
            {
                "spcf": {
                    "L1_application_domain": [
                        {"id": l1, "role": "primary", "confidence": 0.8},
                        {"id": "DOM-006", "role": "secondary", "confidence": 0.7},
                    ],
                    "L2_activity_subdomain": [
                        {"id": l2, "role": "primary", "confidence": 0.8},
                        {"id": "SUB-015", "role": "secondary", "confidence": 0.7},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    accepted_value = "true" if accepted else "false"
    (run_dir / "tasks.md").write_text(
        "---\n"
        "operation: classify\n"
        "confirmed:\n"
        f"  accepted: {accepted_value}\n"
        "---\n"
        "\n"
        "# Операция classify\n",
        encoding="utf-8",
    )
    return run_dir
