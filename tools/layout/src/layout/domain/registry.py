"""Записи реестра происхождения и правило коллизии имени каталога."""

from dataclasses import dataclass


class CollisionError(Exception):
    """Имя каталога в паре слагов занято и не разрешается префиксом организации."""


@dataclass(frozen=True)
class Entry:
    """Действующая запись проекта в реестре происхождения.

    Идентичность записи — имя проекта и организация карточки: повторный прогон
    того же проекта обновляет его запись, а не дополняет реестр.
    """

    name: str
    organization: str | None
    path: str
    l1_id: str
    l1_slug: str
    l2_id: str
    l2_slug: str
    source: str
    date: str

    def as_dict(self) -> dict:
        """Сериализовать запись в словарь реестра."""
        return {
            "name": self.name,
            "organization": self.organization,
            "path": self.path,
            "l1": {"id": self.l1_id, "slug": self.l1_slug},
            "l2": {"id": self.l2_id, "slug": self.l2_slug},
            "source": self.source,
            "date": self.date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entry":
        """Прочитать запись из словаря реестра."""
        return cls(
            name=data["name"],
            organization=data.get("organization"),
            path=data["path"],
            l1_id=data["l1"]["id"],
            l1_slug=data["l1"]["slug"],
            l2_id=data["l2"]["id"],
            l2_slug=data["l2"]["slug"],
            source=data["source"],
            date=data["date"],
        )


def _dir_name(path: str) -> str:
    """Имя каталога проекта — последний сегмент целевого пути."""
    return path.rsplit("/", 1)[-1]


def occupied_dirs(entries: list[Entry], slug_l1: str, slug_l2: str) -> set[str]:
    """Имена каталогов, занятые проектами пары слагов."""
    return {
        _dir_name(entry.path)
        for entry in entries
        if entry.l1_slug == slug_l1 and entry.l2_slug == slug_l2
    }


def resolve_dir_name(
    entries: list[Entry],
    slug_l1: str,
    slug_l2: str,
    name: str,
    organization: str | None,
    current: Entry | None,
) -> str:
    """Разрешить имя каталога проекта в паре слагов.

    Существующая запись проекта сохраняет имя своего каталога, пока пара слагов
    не меняется. Новое имя, занятое другим проектом пары, получает префикс
    организации; занятый префикс — коллизия без разрешения.
    """
    if current is not None and current.l1_slug == slug_l1 and current.l2_slug == slug_l2:
        return _dir_name(current.path)
    taken = occupied_dirs(entries, slug_l1, slug_l2)
    if name not in taken:
        return name
    if not organization:
        raise CollisionError(
            f"имя {name!r} занято в паре {slug_l1}/{slug_l2}, организация для префикса не названа"
        )
    prefixed = f"{organization}-{name}"
    if prefixed in taken:
        raise CollisionError(
            f"заняты и имя {name!r}, и имя с префиксом {prefixed!r} в паре {slug_l1}/{slug_l2}"
        )
    return prefixed
