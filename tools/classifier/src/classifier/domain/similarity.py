"""Косинусная близость и ранжирование кандидатов уровня."""

import math
from dataclasses import dataclass

Vector = list[float]

#: Число кандидатов на уровень: primary + до MAX_SECONDARY secondary.
MAX_CANDIDATES_PER_LEVEL = 4
MAX_SECONDARY = 3


def cosine(a: Vector, b: Vector) -> float:
    """Косинусная близость двух векторов: 1 — совпадение, 0 — независимость."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True)
class Candidate:
    """Кандидат уровня: запись таксономии с близостью и ролью."""

    record_id: str
    confidence: float
    role: str  # "primary" | "secondary"


def rank(record_ids: list[str], vectors: dict[str, Vector], card_vector: Vector) -> list[Candidate]:
    """Ранжировать записи уровня по убыванию близости к вектору карточки.

    Первый кандидат — primary, последующие до MAX_CANDIDATES_PER_LEVEL всего —
    secondary. Пустых placeholder-кандидатов не создаётся.
    """
    scored = [
        (rid, cosine(card_vector, vectors[rid]))
        for rid in record_ids
        if rid in vectors
    ]
    scored.sort(key=lambda item: (-item[1], item[0]))
    top = scored[:MAX_CANDIDATES_PER_LEVEL]
    return [
        Candidate(
            record_id=rid,
            confidence=round(conf, 4),
            role="primary" if i == 0 else "secondary",
        )
        for i, (rid, conf) in enumerate(top)
    ]
