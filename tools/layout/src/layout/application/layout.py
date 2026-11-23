"""Сценарий раскладки: каталог принятого прогона classify → каталоги и реестр."""

import datetime
from dataclasses import dataclass
from pathlib import Path

from layout.domain.path import PathError, target_path
from layout.domain.registry import CollisionError, Entry, resolve_dir_name
from layout.infrastructure.fs import SpaceFileError, SpaceFS, SpaceStateError
from layout.infrastructure.run_reader import RunFileError, RunReader
from layout.infrastructure.taxonomy_codes import (
    TaxonomyCodes,
    TaxonomyFileError,
    TaxonomyLookupError,
)


class LayoutStateError(Exception):
    """Состояние не позволяет выполнить прогон: код возврата 1."""


class LayoutEnvironmentError(Exception):
    """Ошибка вызова или окружения: код возврата 2."""


@dataclass(frozen=True)
class LayoutResult:
    """Итог прогона раскладки."""

    path: str
    created: bool
    registry_updated: bool


def _primary_id(candidates: object, level: str) -> str:
    """Идентификатор primary-кандидата уровня итога классификации."""
    if not isinstance(candidates, list):
        raise LayoutStateError(f"итог классификации не называет кандидатов уровня {level}")
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("role") == "primary":
            return str(candidate["id"])
    raise LayoutStateError(f"итог классификации не называет primary-кандидата уровня {level}")


def layout(run_dir: Path, root: Path, taxonomy_dir: Path) -> LayoutResult:
    """Исполнить раскладку одного проекта по принятому прогону classify."""
    reader = RunReader(run_dir)
    try:
        contracts = reader.read()
    except RunFileError as exc:
        raise LayoutEnvironmentError(str(exc)) from exc
    if not reader.accepted():
        raise LayoutStateError(
            "прогон classify не принят: раскладка фиксирует только присвоенную классификацию"
        )

    card = contracts.card
    name = card.get("name")
    if not isinstance(name, str) or not name:
        raise LayoutStateError("карточка не называет имя проекта")
    facets = card.get("facets")
    organization = facets.get("organization") if isinstance(facets, dict) else None

    spcf = contracts.classification.get("spcf")
    if not isinstance(spcf, dict):
        raise LayoutStateError("итог классификации не несёт блока spcf")
    l1_id = _primary_id(spcf.get("L1_application_domain"), "L1")
    l2_id = _primary_id(spcf.get("L2_activity_subdomain"), "L2")

    codes = TaxonomyCodes(taxonomy_dir)
    try:
        slug_l1 = codes.slug_l1(l1_id)
        slug_l2 = codes.slug_l2(l2_id)
    except TaxonomyLookupError as exc:
        raise LayoutStateError(str(exc)) from exc
    except TaxonomyFileError as exc:
        raise LayoutEnvironmentError(str(exc)) from exc

    space = SpaceFS(root)
    try:
        raw_entries = space.load_registry()
    except SpaceFileError as exc:
        raise LayoutEnvironmentError(str(exc)) from exc
    entries = [Entry.from_dict(item) for item in raw_entries if isinstance(item, dict)]
    current = next(
        (entry for entry in entries if entry.name == name and entry.organization == organization),
        None,
    )

    try:
        dir_name = resolve_dir_name(entries, slug_l1, slug_l2, name, organization, current)
        rel_path = target_path(slug_l1, slug_l2, dir_name)
    except (PathError, CollisionError) as exc:
        raise LayoutStateError(str(exc)) from exc

    try:
        created = space.ensure_directory(rel_path)
    except SpaceStateError as exc:
        raise LayoutStateError(str(exc)) from exc

    entry = Entry(
        name=name,
        organization=organization,
        path=rel_path,
        l1_id=l1_id,
        l1_slug=slug_l1,
        l2_id=l2_id,
        l2_slug=slug_l2,
        source=str(run_dir),
        date=datetime.date.today().isoformat(),
    )
    registry_updated = False
    if current is None:
        entries.append(entry)
        registry_updated = True
    elif current != entry:
        entries[entries.index(current)] = entry
        registry_updated = True
    if registry_updated:
        space.save_registry([item.as_dict() for item in entries])
    return LayoutResult(path=rel_path, created=created, registry_updated=registry_updated)
