"""Тесты HTTP-клиента на фейковом транспорте httpx."""

import httpx
import pytest

from classifier.domain.embeddings import EmbeddingError
from classifier.infrastructure.http_embeddings import HttpEmbeddingClient

VEC = [0.1, 0.2, 0.3]


def _client() -> HttpEmbeddingClient:
    return HttpEmbeddingClient("http://proxy.example/v1", "key", "model-x")


def test_request_format_and_success(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["json"] = __import__("json").loads(request.content)
        return httpx.Response(
            200, json={"data": [{"index": 0, "embedding": VEC}, {"index": 1, "embedding": VEC}]}
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: transport.handle_request(_req(a, kw)))
    client = _client()
    vecs = client.embed(["a", "b"])
    assert vecs == [VEC, VEC]
    assert seen["url"] == "http://proxy.example/v1/embeddings"
    assert seen["auth"] == "Bearer key"
    assert seen["json"] == {"model": "model-x", "input": ["a", "b"]}


def test_endpoint_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: transport.handle_request(_req(a, kw)))
    try:
        _client().embed(["a"])
        raise AssertionError("ожидалась EmbeddingError")
    except EmbeddingError as exc:
        assert "500" in str(exc)


def test_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raiser(*args: object, **kw: object) -> httpx.Response:
        raise httpx.ConnectError("нет соединения")

    monkeypatch.setattr(httpx, "post", raiser)
    try:
        _client().embed(["a"])
        raise AssertionError("ожидалась EmbeddingError")
    except EmbeddingError as exc:
        assert "недоступен" in str(exc)


def test_missing_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDINGS_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDINGS_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDINGS_MODEL", raising=False)
    try:
        HttpEmbeddingClient.from_env()
        raise AssertionError("ожидалась EmbeddingError")
    except EmbeddingError as exc:
        assert "EMBEDDINGS_BASE_URL" in str(exc)


def test_batch_splitting(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content)
        calls.append(body["input"])
        n = len(body["input"])
        return httpx.Response(
            200, json={"data": [{"index": i, "embedding": VEC} for i in range(n)]}
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: transport.handle_request(_req(a, kw)))
    _client().embed([f"t{i}" for i in range(70)])
    assert [len(c) for c in calls] == [64, 6]


def _req(args: tuple, kw: dict) -> httpx.Request:
    """Собрать httpx.Request из позиционного URL и именованных параметров post()."""
    url = args[0] if args else kw["url"]
    return httpx.Request("POST", url, json=kw.get("json"), headers=kw.get("headers"))
