"""Живой прогон прототипа на вымышленных примерах против реального эндпоинта.

Запуск (из tools/classifier): uv run python scripts/live_run.py
Требует переменных окружения EMBEDDINGS_* и каталога taxonomy/ внутри утилиты.
Скрипт одноразовый, в поставку утилиты не входит и кодом не используется.
"""

import json
import sys
from pathlib import Path

from classifier.application.classify import ProjectCard, classify
from classifier.infrastructure.http_embeddings import HttpEmbeddingClient
from classifier.infrastructure.taxonomy_loader import load_taxonomy

EXPORT = Path(__file__).resolve().parents[1] / "taxonomy"
EXAMPLES = EXPORT / "example_project.json"

# Ожидаемая разметка примеров — сравнение из manifest/примера, порог не назначен:
# цель прогона — проверить контракт прокси и порядок кандидатов, не точность.
EXPECTED = {
    "Northstar Market — online store": "DOM-003",
    "Pinecone Goods — catalog hub": "DOM-003",
    "Moss & Maple — product discovery": "DOM-003",
}


def main() -> int:
    taxonomy = load_taxonomy(EXPORT)
    client = HttpEmbeddingClient.from_env()
    examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))["records"]
    for rec in examples:
        card = ProjectCard.from_dict(
            {"name": rec["name"], "purpose": rec["purpose"]}
        )
        output = classify(card, taxonomy, client, threshold=0.5)
        top_l1 = output.spcf["L1_application_domain"][0]
        expected = EXPECTED[rec["name"]]
        mark = "OK " if top_l1.record_id == expected else "MISS"
        print(f"{mark} {rec['name']}")
        print(f"    primary L1: {top_l1.record_id} confidence={top_l1.confidence}")
        for level, candidates in output.spcf.items():
            secondary = ", ".join(
                f"{c.record_id}={c.confidence}" for c in candidates[1:3]
            )
            if secondary:
                print(f"    {level}: secondary {secondary}")
        print(f"    needs_confirmation={output.needs_confirmation}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
