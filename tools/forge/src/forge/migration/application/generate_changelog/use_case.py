"""Сценарий построения changelog из разницы моделей."""

from __future__ import annotations

from typing import Protocol

from forge.migration.application.changelog_storage import ChangelogWriterInterface
from forge.migration.application.constraint_naming import ConstraintNamingInterface
from forge.migration.application.generate_changelog.input import GenerateChangelogInput
from forge.migration.application.generate_changelog.output import (
    ChangeSetView,
    GenerateChangelogOutput,
    ModelViolationView,
    SeedConflictView,
    UnsupportedChangeView,
)
from forge.migration.application.operation_record import OperationRecordReaderInterface
from forge.migration.application.seed_conflicts import SeedConflictCheckerInterface
from forge.migration.domain.changelog import Changelog, ChangeSet
from forge.migration.domain.changes import (
    AddColumn,
    AddForeignKey,
    AddUnique,
    CreateTable,
    DropColumn,
    DropTable,
    DropUnique,
    SchemaChange,
    UnsupportedChangeError,
)
from forge.migration.domain.model_diff import ModelDiff
from forge.modeling.application.load_model.input import LoadModelInput
from forge.modeling.application.load_model.use_case import (
    InvalidModelError,
    LoadModelUseCaseInterface,
)
from forge.modeling.application.model_reading import ModelUnreadableError
from forge.modeling.domain.data_model import DataModel


class AcceptedModelError(Exception):
    """Принятая модель существует, но её не прочитать или она некорректна."""


class DropNotAllowedError(Exception):
    """Модель попытки требует удалений, а беклог операции в `auto` не даёт на них согласия."""

    def __init__(self, objects: tuple[str, ...]) -> None:
        self.objects = objects
        super().__init__("; ".join(objects))


class GenerateChangelogUseCaseInterface(Protocol):
    """Построить changelog попытки."""

    def execute(self, input: GenerateChangelogInput) -> GenerateChangelogOutput: ...


class GenerateChangelogUseCase:
    """Штамп из беклога операции, обе модели, разница, запись changelog.

    Некорректная модель попытки и неподдерживаемые изменения — штатный отказ: changelog
    не пишется, прежний файл удаляется, чтобы устаревший changelog нельзя было накатить.
    Удаления в режиме `auto` без согласия операции — `DropNotAllowedError`, прежний файл тоже
    удаляется; проверка идёт после проверок модели, чтобы агент сначала получил нарушения.
    Удаление набора уникальности или внешнего ключа данных не удаляет и согласия не требует.
    Модель попытки, которой принятый seed не отвечает, — тоже штатный отказ `seed_conflict`
    с удалением прежнего файла; проверка идёт после разницы, до согласия на удаления. Нет
    принятого seed — проверки нет. Ошибки окружения — исключения: `OperationRecordUnavailableError`,
    `ModelUnreadableError` модели попытки, `AcceptedModelError` и `AcceptedSeedError`.
    """

    def __init__(
        self,
        operations: OperationRecordReaderInterface,
        models: LoadModelUseCaseInterface,
        writer: ChangelogWriterInterface,
        diff: ModelDiff,
        naming: ConstraintNamingInterface,
        seeds: SeedConflictCheckerInterface | None = None,
    ) -> None:
        self._operations = operations
        self._models = models
        self._writer = writer
        self._diff = diff
        self._naming = naming
        self._seeds = seeds

    def execute(self, input: GenerateChangelogInput) -> GenerateChangelogOutput:
        record = self._operations.read(input.operation_path)
        stamp = record.stamp
        try:
            attempt = self._models.execute(LoadModelInput(input.model_path)).model
        except InvalidModelError as error:
            self._writer.remove(input.out_path)
            violations = tuple(
                ModelViolationView(v.path, v.code, v.message) for v in error.violations
            )
            return _refused(stamp.logical_file_path, violations=violations)
        accepted = self._accepted(input.accepted_path)
        try:
            changes = self._diff.between(accepted, attempt)
        except UnsupportedChangeError as error:
            self._writer.remove(input.out_path)
            non_additive = tuple(
                UnsupportedChangeView(c.code, c.table, c.column, c.message) for c in error.changes
            )
            return _refused(stamp.logical_file_path, non_additive=non_additive)
        if self._seeds is not None and input.accepted_seed_path is not None:
            conflicts = self._seeds.check(
                input.accepted_seed_path, attempt, _dropped_columns(changes)
            )
            if conflicts:
                self._writer.remove(input.out_path)
                views = tuple(
                    SeedConflictView(c.kind, c.table, c.column, c.path, c.message)
                    for c in conflicts
                )
                return _refused(stamp.logical_file_path, seed_conflict=views)
        dropped = _dropped_objects(changes)
        if dropped and record.mode == "auto" and not record.allow_drop:
            self._writer.remove(input.out_path)
            raise DropNotAllowedError(dropped)
        changelog = Changelog(stamp, changes)
        self._writer.write(input.out_path, changelog)
        return GenerateChangelogOutput(
            changelog_path=input.out_path,
            logical_file_path=changelog.logical_file_path,
            changesets=tuple(self._changeset_view(item) for item in changelog.changesets),
            violations=(),
            non_additive=(),
            generated=True,
        )

    def _accepted(self, path: str) -> DataModel:
        try:
            return self._models.execute(LoadModelInput(path, missing_as_empty=True)).model
        except InvalidModelError as error:
            raise AcceptedModelError(
                f"принятая модель {path} некорректна, нарушений: {len(error.violations)}; "
                f"первое — {error.violations[0].path}: {error.violations[0].message}"
            ) from None
        except ModelUnreadableError as error:
            raise AcceptedModelError(str(error)) from None

    def _changeset_view(self, item: ChangeSet) -> ChangeSetView:
        change = item.change
        if isinstance(change, CreateTable):
            return ChangeSetView(item.id, "create_table", change.table.name.value, None)
        if isinstance(change, AddColumn):
            return ChangeSetView(
                item.id, "add_column", change.table.value, change.column.name.value
            )
        if isinstance(change, DropTable):
            return ChangeSetView(item.id, "drop_table", change.table.name.value, None)
        if isinstance(change, DropColumn):
            return ChangeSetView(
                item.id, "drop_column", change.table.value, change.column.name.value
            )
        if isinstance(change, AddUnique | DropUnique):
            kind = "add_unique" if isinstance(change, AddUnique) else "drop_unique"
            name = self._naming.unique(change.table, change.unique)
            return ChangeSetView(item.id, kind, change.table.value, None, name)
        kind = "add_foreign_key" if isinstance(change, AddForeignKey) else "drop_foreign_key"
        name = self._naming.foreign_key(change.table, change.key)
        return ChangeSetView(item.id, kind, change.table.value, None, name)


def _dropped_objects(changes: tuple[SchemaChange, ...]) -> tuple[str, ...]:
    """Удаляемые объекты: таблица либо `таблица.колонка`."""
    objects: list[str] = []
    for change in changes:
        if isinstance(change, DropTable):
            objects.append(change.table.name.value)
        elif isinstance(change, DropColumn):
            objects.append(f"{change.table.value}.{change.column.name.value}")
    return tuple(objects)


def _dropped_columns(changes: tuple[SchemaChange, ...]) -> tuple[tuple[str, str], ...]:
    """Удаляемые колонки `(таблица, колонка)`."""
    return tuple(
        (change.table.value, change.column.name.value)
        for change in changes
        if isinstance(change, DropColumn)
    )


def _refused(
    logical_file_path: str,
    violations: tuple[ModelViolationView, ...] = (),
    non_additive: tuple[UnsupportedChangeView, ...] = (),
    seed_conflict: tuple[SeedConflictView, ...] = (),
) -> GenerateChangelogOutput:
    return GenerateChangelogOutput(
        changelog_path=None,
        logical_file_path=logical_file_path,
        changesets=(),
        violations=violations,
        non_additive=non_additive,
        generated=False,
        seed_conflict=seed_conflict,
    )
