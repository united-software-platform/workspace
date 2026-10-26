"""Загрузка принятого seed: общая часть сценариев построения changelog данных и сверки seed."""

from __future__ import annotations

from forge.modeling.domain.data_model import DataModel
from forge.seeding.application.seed_reading import (
    SeedDraftReaderInterface,
    SeedNotFoundError,
    SeedUnreadableError,
)
from forge.seeding.domain.factory import SeedFactory
from forge.seeding.domain.seed import Seed, SeedViolationError


class AcceptedSeedError(Exception):
    """Принятый seed существует, но его не прочитать или он не проходит проверку по модели."""


def load_accepted_seed(
    reader: SeedDraftReaderInterface, factory: SeedFactory, model: DataModel, path: str
) -> Seed:
    """Принятый seed по модели; нет файла — seed пуст, иначе ошибка — `AcceptedSeedError`."""
    try:
        reading = reader.read(path)
    except SeedNotFoundError:
        return Seed(())
    except SeedUnreadableError as error:
        raise AcceptedSeedError(str(error)) from None
    try:
        seed = factory.create(model, reading.draft)
    except SeedViolationError as error:
        found = (*reading.violations, *error.violations)
    else:
        found = reading.violations
    if found:
        raise AcceptedSeedError(
            f"принятый seed {path} не проходит проверку по модели, нарушений: {len(found)}; "
            f"первое — {found[0].path}: {found[0].message}"
        )
    return seed
