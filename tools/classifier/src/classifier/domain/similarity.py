"""Косинусная близость и ранжирование кандидатов уровня."""

import math
from dataclasses import dataclass

Vector = list[float]

#: Число secondary-кандидатов на уровень после primary.
MAX_SECONDARY = 3


def cosine(a: Vector, b: Vector) -> float:
    """Косинусная близость двух векторов, зажатая в 0–1.

    Отрицательная корреляция в контракте confidence не допускается — она
    неотличима от независимости для ранжирования и обнуляется.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, dot / (na * nb))


@dataclass(frozen=True)
class Candidate:
    """Кандидат уровня: запись таксономии с близостью и ролью."""

    record_id: str
    confidence: float
    role: str  # "primary" | "secondary"


def rank(record_ids: list[str], vectors: dict[str, Vector], card_vector: Vector) -> list[Candidate]:
    """Ранжировать записи уровня по убыванию близости к вектору карточки.

    Первый кандидат — primary, последующие до 1 + MAX_SECONDARY всего —
    secondary. Пустых placeholder-кандидатов не создаётся. Запись без вектора —
    ошибка контракта, а не молчаливый пропуск.
    """
    scored = [(rid, cosine(card_vector, vectors[rid])) for rid in record_ids]
    scored.sort(key=lambda item: (-item[1], item[0]))
    top = scored[: 1 + MAX_SECONDARY]
    return [
        Candidate(
            record_id=rid,
            confidence=round(conf, 4),
            role="primary" if i == 0 else "secondary",
        )
        for i, (rid, conf) in enumerate(top)
    ]
