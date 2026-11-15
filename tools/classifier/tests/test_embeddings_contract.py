"""Тесты контракта EmbeddingClient и его фейка."""

from classifier.domain.embeddings import EmbeddingError
from tests.fakes import FakeEmbeddingClient


def test_fake_returns_vector_per_text() -> None:
    client = FakeEmbeddingClient()
    vecs = client.embed(["первый текст", "второй текст", "третий"])
    assert len(vecs) == 3
    assert all(len(v) == 8 for v in vecs)


def test_fake_is_deterministic() -> None:
    a = FakeEmbeddingClient().embed(["одинаковый текст"])
    b = FakeEmbeddingClient().embed(["одинаковый текст"])
    assert a == b


def test_fake_records_calls() -> None:
    client = FakeEmbeddingClient()
    client.embed(["текст"])
    assert client.calls == [["текст"]]


def test_fake_failure_raises_domain_error() -> None:
    client = FakeEmbeddingClient(fail=True)
    try:
        client.embed(["текст"])
        raise AssertionError("ожидалась EmbeddingError")
    except EmbeddingError:
        pass
