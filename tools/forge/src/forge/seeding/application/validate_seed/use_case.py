"""Сценарий проверки seed по модели данных."""

from __future__ import annotations

from typing import Protocol

from forge.modeling.application.load_model.input import LoadModelInput
from forge.modeling.application.load_model.use_case import LoadModelUseCaseInterface
from forge.modeling.domain.violation import Violation
from forge.seeding.application.seed_reading import SeedDraftReaderInterface
from forge.seeding.application.validate_seed.input import ValidateSeedInput
from forge.seeding.application.validate_seed.output import ValidateSeedOutput, ViolationView
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.domain.seed import SeedViolationError


class ValidateSeedUseCaseInterface(Protocol):
    """Проверить seed по модели данных и вернуть все нарушения."""

    def execute(self, input: ValidateSeedInput) -> ValidateSeedOutput: ...


class ValidateSeedUseCase:
    """Загружает модель, читает черновик seed и объединяет нарушения структуры и смысла.

    Сначала идут структурные нарушения разборщика, затем нарушения таблиц и строк, затем
    ссылок и циклов — в порядке фабрики. Модель загружается первой: некорректная модель —
    `InvalidModelError`, нечитаемая — `ModelUnreadableError`, нечитаемый seed —
    `SeedUnreadableError`; сценарий их не перехватывает.
    """

    def __init__(
        self,
        models: LoadModelUseCaseInterface,
        reader: SeedDraftReaderInterface,
        factory: SeedFactory,
    ) -> None:
        self._models = models
        self._reader = reader
        self._factory = factory

    def execute(self, input: ValidateSeedInput) -> ValidateSeedOutput:
        model = self._models.execute(
            LoadModelInput(input.model_path, missing_as_empty=input.missing_model_as_empty)
        ).model
        reading = self._reader.read(input.seed_path)
        violations: list[Violation] = list(reading.violations)
        try:
            self._factory.create(model, reading.draft)
        except SeedViolationError as error:
            violations += error.violations
        return ValidateSeedOutput(
            seed_path=input.seed_path,
            model_path=input.model_path,
            valid=not violations,
            violations=tuple(ViolationView(v.path, v.code, v.message) for v in violations),
        )
