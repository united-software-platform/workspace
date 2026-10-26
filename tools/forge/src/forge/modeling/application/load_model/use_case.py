"""Сценарий загрузки модели данных из файла для других контекстов."""

from __future__ import annotations

from typing import Protocol

from forge.modeling.application.load_model.input import LoadModelInput
from forge.modeling.application.load_model.output import LoadModelOutput
from forge.modeling.application.model_reading import (
    DraftReading,
    ModelDraftReaderInterface,
    ModelNotFoundError,
)
from forge.modeling.domain.data_model import DataModel
from forge.modeling.domain.factory import DataModelFactory
from forge.modeling.domain.violation import ModelViolationError, Violation


class InvalidModelError(Exception):
    """Модель в файле нарушает формат: перечислены все нарушения, как у `forge validate`."""

    def __init__(self, path: str, violations: tuple[Violation, ...]) -> None:
        super().__init__(f"модель {path} некорректна: нарушений {len(violations)}")
        self.path = path
        self.violations = violations


class LoadModelUseCaseInterface(Protocol):
    """Загрузить модель данных из файла."""

    def execute(self, input: LoadModelInput) -> LoadModelOutput: ...


class LoadModelUseCase:
    """Читает черновик и строит модель; нарушения формата — `InvalidModelError`.

    Нечитаемый файл — `ModelUnreadableError` контракта чтения. Отсутствующий файл при
    `missing_as_empty` даёт пустую модель: так выглядит принятая модель до первой операции.
    """

    def __init__(self, reader: ModelDraftReaderInterface, factory: DataModelFactory) -> None:
        self._reader = reader
        self._factory = factory

    def execute(self, input: LoadModelInput) -> LoadModelOutput:
        try:
            reading: DraftReading = self._reader.read(input.model_path)
        except ModelNotFoundError:
            if not input.missing_as_empty:
                raise
            return LoadModelOutput(DataModel(()), found=False)
        violations: list[Violation] = list(reading.violations)
        model: DataModel | None = None
        try:
            model = self._factory.create(reading.draft)
        except ModelViolationError as error:
            violations += error.violations
        if violations or model is None:
            raise InvalidModelError(input.model_path, tuple(violations))
        return LoadModelOutput(model, found=True)
