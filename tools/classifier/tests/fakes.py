"""Фейковый клиент embeddings для тестов: сети нет, векторы детерминированы."""

from typing import ClassVar

from classifier.domain.embeddings import EmbeddingError

# Детерминированные хэш-векторы фиксированной размерности: одинаковый текст —
# одинаковый вектор, разные тексты почти ортогональны.
DIM = 8
PP = 2**31 - 1
BASES = [[(i * 131 + j * 37) % 251 - 125 for j in range(DIM)] for i in range(64)]


def _stable_vector(text: str) -> list[float]:
    seed = 0
    for ch in text:
        seed = (seed * 31 + ord(ch)) % PP
    vec = BASES[seed % len(BASES)]
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


class FakeEmbeddingClient:
    """Фейк контракта EmbeddingClient: векторы из хэша текста."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingError("фейк: эндпоинт недоступен")
        self.calls.append(texts)
        return [_stable_vector(t) for t in texts]


class SimilarFakeEmbeddingClient(FakeEmbeddingClient):
    """Фейк с управляемой близостью: пара ключевых слов задаёт вектор."""

    # Словарь «ключевое слово → базисный вектор»; текст комбинирует базисы своих слов
    KEYWORDS: ClassVar[dict[str, int]] = {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        vecs: list[list[float]] = []
        for text in texts:
            acc = [0.0] * DIM
            lowered = text.lower()
            hit = False
            for word, idx in self.KEYWORDS.items():
                if word in lowered:
                    hit = True
                    for j in range(DIM):
                        acc[j] += BASES[idx % len(BASES)][j]
            if not hit:
                acc = _stable_vector(text)
            norm = sum(v * v for v in acc) ** 0.5 or 1.0
            vecs.append([v / norm for v in acc])
        return vecs
