"""Сценарий использования: классификация карточки проекта по уровням L1–L4."""

from dataclasses import dataclass, field

from classifier.domain.embeddings import EmbeddingClient, EmbeddingError
from classifier.domain.similarity import MARGIN, Candidate, rank
from classifier.domain.taxonomy import LEVELS, TaxonomyRecord

#: Фасеты, входящие в текст сопоставления карточки.
_SIGNIFICANT_FACETS = ("domains", "technologies", "roles", "status", "origin")


class ClassificationError(Exception):
    """Ошибка классификации: карточка непригодна."""


@dataclass(frozen=True)
class ProjectCard:
    """Входной контракт: карточка проекта.

    purpose обязателен; facets опционален; неизвестные поля игнорируются.
    """

    name: str
    purpose: str
    facets: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectCard":
        """Собрать карточку из разобранного JSON.

        Пустой purpose допустим: карточка собирается, а classify() возвращает
        needs_confirmation без обращения к эндпоинту.

        Raises:
            ClassificationError: данные не объект, purpose не строка или facets
                не объект.
        """
        if not isinstance(data, dict):
            raise ClassificationError("карточка не является JSON-объектом")
        purpose = data.get("purpose", "")
        if not isinstance(purpose, str):
            raise ClassificationError("поле purpose не является строкой")
        facets = data.get("facets")
        if facets is None:
            facets = {}
        if not isinstance(facets, dict):
            raise ClassificationError("поле facets не является объектом")
        return cls(name=str(data.get("name", "")), purpose=purpose, facets=dict(facets))

    def has_purpose(self) -> bool:
        """Назначение проекта заполнено."""
        return bool(self.purpose.strip())

    def text(self) -> str:
        """Текст карточки для векторизации: purpose и значимые фасеты без пустых."""
        parts: list[str] = [self.purpose.strip()]
        for facet in _SIGNIFICANT_FACETS:
            value = self.facets.get(facet)
            if isinstance(value, list) and value:
                parts.append(f"{facet}: " + ", ".join(str(v) for v in value))
            elif isinstance(value, str) and value.strip():
                parts.append(f"{facet}: {value.strip()}")
        return "\n".join(parts)


@dataclass(frozen=True)
class ClassificationOutput:
    """Выходной контракт: итог классификации по уровням L1–L4.

    `combined_labels` — метки «A & B» уровней с малым отрывом: ключ уровня,
    значение — склейка имён кандидатов в пределах margin. Малый отрыв
    подтверждения не требует: обе гипотезы уже в списке кандидатов.
    """

    spcf: dict[str, list[Candidate]]
    needs_confirmation: bool
    reasons: list[str]
    rationale: str
    combined_labels: dict[str, str] = field(default_factory=dict)


def _level_names(taxonomy: dict[str, list[TaxonomyRecord]]) -> dict[str, str]:
    """Имя записи по её идентификатору — для rationale и причин."""
    return {
        record.record_id: f"{record.name_ru} ({record.record_id})"
        for records in taxonomy.values()
        for record in records
    }


def classify(
    card: ProjectCard,
    taxonomy: dict[str, list[TaxonomyRecord]],
    client: EmbeddingClient,
    threshold: float = 0.5,
) -> ClassificationOutput:
    """Классифицировать карточку: векторизация, ранжирование, выходной контракт.

    Пустой purpose — без обращения к эндпоинту: контракт с needs_confirmation=true
    и пустыми уровнями.

    Raises:
        EmbeddingError: эндпоинт недоступен или вернул непригодный ответ.
    """
    if not card.has_purpose():
        return ClassificationOutput(
            spcf={level: [] for level in LEVELS},
            needs_confirmation=True,
            reasons=["поле purpose пусто — данных для сопоставления нет"],
            rationale=(
                "Назначение проекта не раскрыто: классификация не выполнялась, "
                "записи уровней не предлагаются."
            ),
        )
    names = _level_names(taxonomy)

    # Один батч на все записи таксономии, один запрос на карточку (design D3)
    record_ids: list[str] = []
    vectors: dict[str, list[float]] = {}
    record_texts: list[str] = []
    for level, records in taxonomy.items():
        for record in records:
            record_ids.append(record.record_id)
            record_texts.append(record.text())
    embedded = client.embed(record_texts)
    if len(embedded) != len(record_texts):
        raise EmbeddingError(
            f"эндпоинт вернул {len(embedded)} векторов на {len(record_texts)} текстов"
        )
    for rid, vec in zip(record_ids, embedded, strict=True):
        vectors[rid] = vec

    card_vector = client.embed([card.text()])[0]

    spcf: dict[str, list[Candidate]] = {}
    reasons: list[str] = []
    combined_labels: dict[str, str] = {}
    for level in LEVELS:
        level_ids = [r.record_id for r in taxonomy[level]]
        candidates = rank(level_ids, vectors, card_vector)
        spcf[level] = candidates
        if candidates and candidates[0].confidence < threshold:
            top = candidates[0]
            reasons.append(
                f"primary {level} {names[top.record_id]} ниже порога {threshold}: "
                f"{top.confidence}"
            )
        # Малый отрыв primary от второго — не отказ, а метка «A & B»:
        # кандидаты в пределах margin соединяются общей меткой уровня.
        # Единственный кандидат уровня отрыва не даёт.
        if len(candidates) > 1:
            margin_gap = candidates[0].confidence - candidates[1].confidence
            if margin_gap < MARGIN:
                within = [c for c in candidates
                          if candidates[0].confidence - c.confidence < MARGIN]
                within = within[:3]
                label = " & ".join(names[c.record_id] for c in within)
                combined_labels[level] = label

    needs_confirmation = bool(reasons)
    if needs_confirmation:
        rationale = (
            "Сопоставление по purpose и значимым фасетам; "
            + "; ".join(reasons)
            + " — данных карточки для уверенной классификации недостаточно."
        )
    else:
        tops = ", ".join(names[c[0].record_id] for c in spcf.values() if c)
        rationale = (
            f"Сопоставление по purpose и значимым фасетам; лучшие кандидаты уровней: {tops}."
        )
    if combined_labels:
        joined = "; ".join(f"{level}: {label}" for level, label in combined_labels.items())
        rationale += f" Пограничные уровни — объединённые метки: {joined}."
    return ClassificationOutput(
        spcf=spcf,
        needs_confirmation=needs_confirmation,
        reasons=reasons,
        rationale=rationale,
        combined_labels=combined_labels,
    )
