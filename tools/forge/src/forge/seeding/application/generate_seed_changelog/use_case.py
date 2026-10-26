"""Сценарий построения changelog данных из разницы seed."""

from __future__ import annotations

from typing import Protocol

from forge.migration.application.generate_changelog.use_case import (
    AcceptedModelError,
    DropNotAllowedError,
)
from forge.migration.application.operation_record import OperationRecordReaderInterface
from forge.modeling.application.load_model.input import LoadModelInput
from forge.modeling.application.load_model.use_case import (
    InvalidModelError,
    LoadModelUseCaseInterface,
)
from forge.modeling.domain.data_model import DataModel
from forge.modeling.domain.violation import Violation
from forge.seeding.application.accepted_seed import load_accepted_seed
from forge.seeding.application.data_changelog_storage import DataChangelogWriterInterface
from forge.seeding.application.generate_seed_changelog.input import GenerateSeedChangelogInput
from forge.seeding.application.generate_seed_changelog.output import (
    DataChangeSetView,
    DeletedRowView,
    GenerateSeedChangelogOutput,
    SeedViolationView,
    UnsupportedRowChangeView,
)
from forge.seeding.application.seed_reading import SeedDraftReaderInterface
from forge.seeding.domain.data_changelog import DataChangelog
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.domain.row_changes import UnsupportedRowChangeError, row_label
from forge.seeding.domain.seed import Seed, SeedViolationError
from forge.seeding.domain.seed_diff import SeedDiff

_KINDS = {"insert": "insert_rows", "update": "update_rows", "delete": "delete_rows"}


class GenerateSeedChangelogUseCaseInterface(Protocol):
    """Построить changelog данных попытки."""

    def execute(self, input: GenerateSeedChangelogInput) -> GenerateSeedChangelogOutput: ...


class GenerateSeedChangelogUseCase:
    """Штамп из беклога операции, модель, оба seed, разница, запись changelog данных.

    Оба seed проверяются по одной модели, как у `forge validate-seed`. Нарушения seed попытки
    и неисполнимые изменения строк — штатный отказ: changelog не пишется, прежний файл
    удаляется, чтобы устаревший changelog нельзя было накатить. Удаления строк в режиме
    `auto` без согласия операции — `DropNotAllowedError`, прежний файл тоже удаляется.
    Ошибки окружения — исключения: `OperationRecordUnavailableError`, `ModelUnreadableError`,
    `SeedUnreadableError` seed попытки, `AcceptedModelError` и `AcceptedSeedError`.
    """

    def __init__(
        self,
        operations: OperationRecordReaderInterface,
        models: LoadModelUseCaseInterface,
        reader: SeedDraftReaderInterface,
        writer: DataChangelogWriterInterface,
        factory: SeedFactory,
        diff: SeedDiff,
    ) -> None:
        self._operations = operations
        self._models = models
        self._reader = reader
        self._writer = writer
        self._factory = factory
        self._diff = diff

    def execute(self, input: GenerateSeedChangelogInput) -> GenerateSeedChangelogOutput:
        record = self._operations.read(input.operation_path)
        logical = record.stamp.logical_file_path
        model = self._model(input)
        reading = self._reader.read(input.seed_path)
        violations: list[Violation] = list(reading.violations)
        try:
            attempt = self._factory.create(model, reading.draft)
        except SeedViolationError as error:
            violations += error.violations
        if violations:
            self._writer.remove(input.out_path)
            views = tuple(SeedViolationView(v.path, v.code, v.message) for v in violations)
            return _refused(logical, violations=views)
        accepted = self._accepted(model, input.accepted_seed_path)
        try:
            groups = self._diff.between(accepted, attempt)
        except UnsupportedRowChangeError as error:
            self._writer.remove(input.out_path)
            unsupported = tuple(
                UnsupportedRowChangeView(c.code, c.table, c.columns, c.rows, c.message)
                for c in error.changes
            )
            return _refused(logical, unsupported=unsupported)
        changelog = DataChangelog(record.stamp, groups)
        deleted = changelog.deleted_rows()
        if deleted and record.mode == "auto" and not record.allow_drop:
            self._writer.remove(input.out_path)
            raise DropNotAllowedError(tuple(row_label(d.table, d.row) for d in deleted))
        self._writer.write(input.out_path, changelog)
        return GenerateSeedChangelogOutput(
            changelog_path=input.out_path,
            logical_file_path=changelog.logical_file_path,
            changesets=tuple(
                DataChangeSetView(
                    item.id,
                    _KINDS[item.group.kind.value],
                    item.group.table.name.value,
                    len(item.group.changes),
                )
                for item in changelog.changesets
            ),
            deleted_rows=tuple(
                DeletedRowView(
                    d.table.name.value,
                    tuple((column.value, value.value) for column, value in d.key()),
                )
                for d in deleted
            ),
            violations=(),
            unsupported=(),
            generated=True,
        )

    def _model(self, input: GenerateSeedChangelogInput) -> DataModel:
        request = LoadModelInput(input.model_path, missing_as_empty=input.missing_model_as_empty)
        try:
            return self._models.execute(request).model
        except InvalidModelError as error:
            raise AcceptedModelError(
                f"модель {input.model_path} некорректна, нарушений: {len(error.violations)}; "
                f"первое — {error.violations[0].path}: {error.violations[0].message}"
            ) from None

    def _accepted(self, model: DataModel, path: str) -> Seed:
        return load_accepted_seed(self._reader, self._factory, model, path)


def _refused(
    logical_file_path: str,
    violations: tuple[SeedViolationView, ...] = (),
    unsupported: tuple[UnsupportedRowChangeView, ...] = (),
) -> GenerateSeedChangelogOutput:
    return GenerateSeedChangelogOutput(
        changelog_path=None,
        logical_file_path=logical_file_path,
        changesets=(),
        deleted_rows=(),
        violations=violations,
        unsupported=unsupported,
        generated=False,
    )
