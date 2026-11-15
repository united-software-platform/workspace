"""Тесты косинусной близости и ранжирования на фиксированных векторах."""

from classifier.domain.similarity import cosine, rank

# Ортогональные базисы 4-мерного пространства
E1 = [1.0, 0.0, 0.0, 0.0]
E2 = [0.0, 1.0, 0.0, 0.0]
E3 = [0.0, 0.0, 1.0, 0.0]


def test_cosine_identical() -> None:
    assert cosine(E1, E1) == 1.0


def test_cosine_orthogonal() -> None:
    assert cosine(E1, E2) == 0.0


def test_cosine_negative_clamped_to_zero() -> None:
    # Антикоррелированные векторы: confidence в контракте не бывает отрицательным
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_cosine_zero_vector() -> None:
    assert cosine([0.0, 0.0, 0.0, 0.0], E1) == 0.0


def test_rank_order_and_roles() -> None:
    card = [1.0, 0.5, 0.0, 0.0]
    vectors = {"A": E1, "B": E2, "C": E3}
    result = rank(["A", "B", "C"], vectors, card)
    assert [c.record_id for c in result] == ["A", "B", "C"]
    assert [c.role for c in result] == ["primary", "secondary", "secondary"]
    assert result[0].confidence >= result[1].confidence >= result[2].confidence


def test_rank_caps_candidates() -> None:
    # 1 primary + MAX_SECONDARY secondary
    vectors = {f"V{i}": E1 for i in range(10)}
    result = rank(list(vectors), vectors, E1)
    assert len(result) == 4
    assert [c.role for c in result] == ["primary", "secondary", "secondary", "secondary"]


def test_rank_missing_vector_raises() -> None:
    # Запись без вектора — ошибка контракта, не молчаливый пропуск
    vectors = {"A": E1}
    try:
        rank(["A", "B"], vectors, E1)
        raise AssertionError("ожидался KeyError")
    except KeyError as exc:
        assert "B" in str(exc)


def test_rank_fewer_than_limit_no_placeholders() -> None:
    vectors = {"A": E1}
    result = rank(["A"], vectors, E1)
    assert [c.record_id for c in result] == ["A"]
    assert result[0].role == "primary"


def test_rank_deterministic_ties() -> None:
    # Равная близость — стабильный порядок по идентификатору
    vectors = {"B": E1, "A": E1}
    result = rank(["B", "A"], vectors, E1)
    assert [c.record_id for c in result] == ["A", "B"]
