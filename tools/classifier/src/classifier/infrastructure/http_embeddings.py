"""HTTP-клиент OpenAI-совместимого эндпоинта embeddings за прокси."""

import os

import httpx

from classifier.domain.embeddings import EmbeddingError

_TIMEOUT = httpx.Timeout(60.0)


class HttpEmbeddingClient:
    """Реализация контракта EmbeddingClient поверх POST {base}/embeddings.

    Параметры берутся из окружения: EMBEDDINGS_BASE_URL, EMBEDDINGS_API_KEY,
    EMBEDDINGS_MODEL. Батч режется на части по _MAX_BATCH текстов — лимит
    прокси на размер запроса не должен ломать прогон таксономии.
    """

    _MAX_BATCH = 64

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        base = base_url.rstrip("/")
        # Прокси выставляет OpenAI-контракт под /v1: дописываем суффикс, если его нет
        if not base.endswith("/v1"):
            base += "/v1"
        self._base_url = base
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_env(cls) -> "HttpEmbeddingClient":
        """Собрать клиент из переменных окружения EMBEDDINGS_*.

        Raises:
            EmbeddingError: любая из переменных не задана.
        """
        base_url = os.environ.get("EMBEDDINGS_BASE_URL", "")
        api_key = os.environ.get("EMBEDDINGS_API_KEY", "")
        model = os.environ.get("EMBEDDINGS_MODEL", "")
        missing = [
            name
            for name, value in (
                ("EMBEDDINGS_BASE_URL", base_url),
                ("EMBEDDINGS_API_KEY", api_key),
                ("EMBEDDINGS_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise EmbeddingError(f"не заданы переменные окружения: {', '.join(missing)}")
        return cls(base_url, api_key, model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Вернуть векторы текстов; порядок соответствует входному списку."""
        result: list[list[float]] = []
        for start in range(0, len(texts), self._MAX_BATCH):
            chunk = texts[start : start + self._MAX_BATCH]
            result.extend(self._embed_chunk(chunk))
        return result

    def _embed_chunk(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self._model, "input": texts}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = httpx.post(
                f"{self._base_url}/embeddings",
                json=payload,
                headers=headers,
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"эндпоинт недоступен: {exc}") from exc
        if response.status_code != 200:
            raise EmbeddingError(
                f"эндпоинт вернул {response.status_code}: {response.text[:200]}"
            )
        try:
            data = response.json()["data"]
            vectors = {item["index"]: item["embedding"] for item in data}
            return [vectors[i] for i in range(len(texts))]
        except (KeyError, ValueError, TypeError) as exc:
            raise EmbeddingError(f"непригодный ответ эндпоинта: {exc}") from exc
