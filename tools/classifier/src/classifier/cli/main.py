"""Точка входа CLI классификатора доменов.

Коды возврата: 0 — порог пройден, 1 — needs_confirmation, 2 — ошибка входа
или окружения (карточка, выгрузка, переменные, эндпоинт).
"""

import argparse
import json
import os
import sys
from pathlib import Path

from classifier.application.classify import ClassificationError, ProjectCard, classify
from classifier.domain.embeddings import EmbeddingClient, EmbeddingError
from classifier.domain.taxonomy import TaxonomyError
from classifier.infrastructure.http_embeddings import HttpEmbeddingClient
from classifier.infrastructure.stub_embeddings import StubEmbeddingClient
from classifier.infrastructure.taxonomy_loader import load_taxonomy

#: Каталог выгрузки таксономии, поставляемой вместе с утилитой.
_EXPORT_DIR = Path(__file__).resolve().parents[3] / "taxonomy"


def _build_client() -> EmbeddingClient:
    """Собрать клиент embeddings из окружения.

    CLASSIFIER_EMBEDDINGS=stub — детерминированный фейк без сети для интеграционных
    тестов; отсутствие значения — живой эндпоинт по EMBEDDINGS_*.
    """
    if os.environ.get("CLASSIFIER_EMBEDDINGS") == "stub":
        return StubEmbeddingClient()
    return HttpEmbeddingClient.from_env()


def build_parser() -> argparse.ArgumentParser:
    """Собрать парсер аргументов CLI."""
    parser = argparse.ArgumentParser(
        prog="classifier",
        description="Классификация карточки проекта по таксономии SPCF 2.0 (уровни L1–L4)",
    )
    parser.add_argument("card", help="путь к файлу карточки проекта в формате JSON")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="порог confidence для primary-кандидата уровня (по умолчанию 0.5)",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="каталог выгрузки таксономии (по умолчанию taxonomy внутри утилиты)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Исполнить CLI-прогон классификации."""
    args = build_parser().parse_args(argv)
    export_dir = args.export_dir or _EXPORT_DIR
    try:
        raw = json.loads(Path(args.card).read_text(encoding="utf-8"))
        card = ProjectCard.from_dict(raw)
        taxonomy = load_taxonomy(export_dir)
        client = _build_client()
        output = classify(card, taxonomy, client, threshold=args.threshold)
    except ClassificationError as exc:
        print(f"ошибка карточки: {exc}", file=sys.stderr)
        return 2
    except TaxonomyError as exc:
        print(f"ошибка выгрузки таксономии: {exc}", file=sys.stderr)
        return 2
    except EmbeddingError as exc:
        print(f"ошибка эндпоинта embeddings: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"ошибка входа: {exc}", file=sys.stderr)
        return 2

    payload = {
        "spcf": {
            level: [
                {"id": c.record_id, "role": c.role, "confidence": c.confidence}
                for c in candidates
            ]
            for level, candidates in output.spcf.items()
        },
        "needs_confirmation": output.needs_confirmation,
        "reasons": output.reasons,
        "rationale": output.rationale,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 1 if output.needs_confirmation else 0


if __name__ == "__main__":
    sys.exit(main())
