"""Вычисление целевого пути раскладки по primary-меткам."""

import re

#: Пригодный сегмент пути: строчные латинские буквы, цифры и дефис.
SEGMENT_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class PathError(Exception):
    """Целевой путь невычислим: сегмент непригоден, преобразование запрещено."""


def target_path(slug_l1: str, slug_l2: str, project_dir: str) -> str:
    """Собрать целевой путь относительно корня рабочего пространства.

    Слаги уровней и имя каталога берутся как есть: значение, не проходящее
    условие сегмента, прекращает вычисление — транслитерация, нормализация
    и усечение не выполняются.
    """
    segments = (("слаг L1", slug_l1), ("слаг L2", slug_l2), ("имя каталога", project_dir))
    for label, value in segments:
        if not SEGMENT_PATTERN.match(value):
            raise PathError(
                f"{label} непригодно как сегмент пути: {value!r}; значение не преобразуется"
            )
    return f"projects/{slug_l1}/{slug_l2}/{project_dir}"
