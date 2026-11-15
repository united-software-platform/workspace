"""Детерминированный фейковый клиент embeddings без сети.

Включается значением CLASSIFIER_EMBEDDINGS=stub в CLI: интеграционные тесты
прогоняют полный путь команды без обращений к эндпоинту.
"""

from classifier.domain.embeddings import EmbeddingError

_DIM = 64
_PP = 2**31 - 1


def _stable_vector(text: str) -> list[float]:
    """Вектор из хэша текста: одинаковый текст — одинаковый вектор."""
    seed = 0
    for ch in text:
        seed = (seed * 131 + ord(ch)) % _PP
    vec = [((seed >> (i % 24)) + i * 37) % 251 - 125 for i in range(_DIM)]
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


class StubEmbeddingClient:
    """Реализация контракта EmbeddingClient на детерминированных векторах."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Вернуть вектор на каждый текст; размер всегда совпадает."""
        if not texts:
            raise EmbeddingError("пустой список текстов")
        return [_stable_vector(t) for t in texts]
