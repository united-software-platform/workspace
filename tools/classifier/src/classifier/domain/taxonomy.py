"""Доменные сущности таксономии SPCF 2.0."""

from dataclasses import dataclass

#: Уровни таксономии в порядке L1 → L4: ключ выходного контракта и файл выгрузки.
LEVELS: dict[str, str] = {
    "L1_application_domain": "l1_application_domains.json",
    "L2_activity_subdomain": "l2_activity_subdomains.json",
    "L3_problem_domain": "l3_problem_domains.json",
    "L4_solution_archetype": "l4_solution_archetypes.json",
}

#: Префиксы идентификаторов записей уровней.
ID_PREFIXES: dict[str, str] = {
    "L1_application_domain": "DOM",
    "L2_activity_subdomain": "SUB",
    "L3_problem_domain": "PRB",
    "L4_solution_archetype": "SOL",
}


class TaxonomyError(Exception):
    """Ошибка выгрузки таксономии: файл отсутствует, не читается или неполон."""


@dataclass(frozen=True)
class TaxonomyRecord:
    """Запись уровня таксономии с двуязычными полями."""

    level: str
    record_id: str
    code: str
    name: str
    name_ru: str
    description: str
    description_ru: str

    def text(self) -> str:
        """Текст записи для векторизации: склейка двуязычных полей."""
        return f"{self.name} | {self.name_ru} | {self.description} | {self.description_ru}"
