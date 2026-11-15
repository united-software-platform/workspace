"""Тесты сценария классификации на фейковом клиенте embeddings."""

import pytest

from classifier.application.classify import (
    ClassificationError,
    ProjectCard,
    classify,
)
from classifier.domain.taxonomy import LEVELS, TaxonomyRecord
from tests.fakes import FakeEmbeddingClient, SimilarFakeEmbeddingClient


def _record(level: str, rid: str, name_ru: str, text_words: str) -> TaxonomyRecord:
    return TaxonomyRecord(
        level=level,
        record_id=rid,
        code="x",
        name=text_words,
        name_ru=name_ru,
        description=text_words,
        description_ru=text_words,
    )


def _taxonomy() -> dict[str, list[TaxonomyRecord]]:
    return {
        "L1_application_domain": [
            _record("L1_application_domain", "DOM-003", "Торговля", "commerce retail store"),
            _record("L1_application_domain", "DOM-005", "Геномика", "genomics dna genes"),
        ],
        "L2_activity_subdomain": [
            _record("L2_activity_subdomain", "SUB-004", "Продажи", "sales checkout orders"),
            _record("L2_activity_subdomain", "SUB-022", "Аналитика", "analytics reports"),
        ],
        "L3_problem_domain": [
            _record("L3_problem_domain", "PRB-002", "Неэффективность", "inefficiency process"),
            _record("L3_problem_domain", "PRB-019", "Поиск", "search retrieval"),
        ],
        "L4_solution_archetype": [
            _record("L4_solution_archetype", "SOL-031", "Платформа", "platform service"),
            _record("L4_solution_archetype", "SOL-006", "Библиотека", "library sdk"),
        ],
    }


CARD = ProjectCard(
    name="novamart-checkout",
    purpose="Сервис оформления заказа магазина: корзина, оплата",
    facets={"domains": ["ecommerce"], "technologies": ["go", "postgresql"]},
)


def test_card_text_purpose_and_significant_facets() -> None:
    text = CARD.text()
    assert "корзина" in text and "ecommerce" in text and "go" in text
    assert "organization" not in text and "customer" not in text


def test_card_rejects_missing_purpose() -> None:
    with pytest.raises(ClassificationError, match="purpose"):
        ProjectCard.from_dict({"purpose": 42})


def test_empty_purpose_needs_confirmation_without_endpoint() -> None:
    client = FakeEmbeddingClient()
    card = ProjectCard.from_dict({"name": "x", "purpose": ""})
    output = classify(card, _taxonomy(), client)
    assert output.needs_confirmation is True
    assert client.calls == [], "эндпоинт не вызывался"
    assert all(cands == [] for cands in output.spcf.values())
    assert "purpose" in output.reasons[0]


def test_card_rejects_non_object() -> None:
    with pytest.raises(ClassificationError, match="объект"):
        ProjectCard.from_dict([1, 2])


def test_card_accepts_minimal() -> None:
    card = ProjectCard.from_dict({"purpose": "описание"})
    assert card.purpose == "описание" and card.facets == {}


def test_classify_threshold_passed() -> None:
    client = SimilarFakeEmbeddingClient()
    # Ключевые слова карточки направляют к primary-записям каждого уровня
    client.KEYWORDS = {
        "заказ": 0, "магазин": 0, "commerce": 0, "retail": 0, "store": 0,
        "sales": 0, "inefficiency": 0, "platform": 0, "genomics": 1, "dna": 1,
    }
    output = classify(CARD, _taxonomy(), client, threshold=0.1)
    assert output.needs_confirmation is False
    assert output.reasons == []
    assert output.spcf["L1_application_domain"][0].record_id == "DOM-003"
    assert "Торговля" in output.rationale


def test_classify_threshold_not_passed() -> None:
    output = classify(CARD, _taxonomy(), FakeEmbeddingClient(), threshold=0.99)
    assert output.needs_confirmation is True
    assert output.reasons, "причины ниже порога названы"
    assert "недостаточно" in output.rationale
    assert all(len(cands) <= 4 for cands in output.spcf.values())


def test_classify_batches_taxonomy_single_call_for_card() -> None:
    client = FakeEmbeddingClient()
    classify(CARD, _taxonomy(), client, threshold=0.0)
    # Первый вызов — все записи таксономии одним батчем, второй — карточка
    assert len(client.calls) == 2
    assert len(client.calls[0]) == sum(len(v) for v in _taxonomy().values())
    assert client.calls[1] == [CARD.text()]


def test_classify_levels_shape() -> None:
    output = classify(CARD, _taxonomy(), FakeEmbeddingClient(), threshold=0.0)
    assert set(output.spcf) == set(LEVELS)
    for candidates in output.spcf.values():
        roles = [c.role for c in candidates]
        assert roles[0] == "primary"
        assert all(r == "secondary" for r in roles[1:])
