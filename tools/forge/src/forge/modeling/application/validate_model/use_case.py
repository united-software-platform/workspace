"""Сценарий проверки модели данных."""

from __future__ import annotations

from typing import Protocol

from forge.modeling.application.model_reading import ModelDraftReaderInterface
from forge.modeling.application.validate_model.input import ValidateModelInput
from forge.modeling.application.validate_model.output import ValidateModelOutput, ViolationView
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.domain.violation import ModelViolationError, Violation


class ValidateModelUseCaseInterface(Protocol):
    """Проверить модель данных и вернуть все нарушения."""

    def execute(self, input: ValidateModelInput) -> ValidateModelOutput: ...


class ValidateModelUseCase:
    """Читает черновик, строит из него модель и объединяет нарушения обоих уровней.

    Нечитаемый файл — `ModelUnreadableError` контракта чтения, сценарий его не перехватывает.
    """

    def __init__(self, reader: ModelDraftReaderInterface, factory: DataModelFactory) -> None:
        self._reader = reader
        self._factory = factory

    def execute(self, input: ValidateModelInput) -> ValidateModelOutput:
        reading = self._reader.read(input.model_path)
        violations: list[Violation] = list(reading.violations)
        try:
            self._factory.create(reading.draft)
        except ModelViolationError as error:
            violations += error.violations
        return ValidateModelOutput(
            model_path=input.model_path,
            valid=not violations,
            violations=tuple(ViolationView(v.path, v.code, v.message) for v in violations),
        )
