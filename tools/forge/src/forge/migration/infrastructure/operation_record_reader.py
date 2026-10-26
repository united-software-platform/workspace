"""Чтение записи об операции из фронтматтера беклога операции.

Anti-Corruption Layer к беклогу контекста Операция: из фронтматтера берутся только `subject`,
`mode`, `allow_drop`, `verdict.attempt_N` и `trail.attempt_N`. Беклог без блока `trail`
(шаблон 1.0.0) получает каталоги попыток по раскладке следа, беклог без `allow_drop` — `False`.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

import yaml

from forge.migration.application.operation_record import (
    OperationRecord,
    OperationRecordUnavailableError,
)
from forge.migration.domain.stamp import InvalidStampError, OperationStamp

ATTEMPTS = (1, 2, 3)
_VERDICTS = ("success", "failure", None)
_MODES = ("auto", "interactive")


class FrontmatterOperationRecordReader:
    """Реализация контракта чтения записи об операции по фронтматтеру YAML."""

    def read(self, path: str) -> OperationRecord:
        try:
            with open(path, encoding="utf-8") as file:
                text = file.read()
        except (OSError, UnicodeDecodeError) as error:
            raise OperationRecordUnavailableError(
                f"беклог операции {path} не прочитать: {error}"
            ) from None
        frontmatter = _frontmatter(path, text)
        try:
            stamp = OperationStamp(str(frontmatter.get("subject", "")))
        except InvalidStampError as error:
            raise OperationRecordUnavailableError(f"беклог операции {path}: {error}") from None
        return OperationRecord(
            stamp=stamp,
            verdicts={attempt: _verdict(path, frontmatter, attempt) for attempt in ATTEMPTS},
            trail_directory=str(PurePosixPath(path).parent),
            attempt_directories=_trail(path, frontmatter),
            mode=_mode(path, frontmatter),
            allow_drop=_allow_drop(path, frontmatter),
        )


def _frontmatter(path: str, text: str) -> dict[str, Any]:
    lines = text.splitlines()
    bounds = [index for index, line in enumerate(lines) if line.strip() == "---"][:2]
    if len(bounds) < 2:
        raise OperationRecordUnavailableError(f"в беклоге операции {path} нет фронтматтера")
    try:
        data = yaml.safe_load("\n".join(lines[bounds[0] + 1 : bounds[1]]))
    except yaml.YAMLError as error:
        raise OperationRecordUnavailableError(
            f"фронтматтер беклога операции {path} не разбирается: {error}"
        ) from None
    if not isinstance(data, dict):
        raise OperationRecordUnavailableError(
            f"фронтматтер беклога операции {path} не является отображением"
        )
    return data


def _mode(path: str, frontmatter: dict[str, Any]) -> str | None:
    value = frontmatter.get("mode")
    if value is not None and value not in _MODES:
        raise OperationRecordUnavailableError(
            f"беклог операции {path}: mode должен быть auto или interactive, получено {value!r}"
        )
    return value


def _allow_drop(path: str, frontmatter: dict[str, Any]) -> bool:
    value = frontmatter.get("allow_drop", False)
    if not isinstance(value, bool):
        raise OperationRecordUnavailableError(
            f"беклог операции {path}: allow_drop должен быть true или false, получено {value!r}"
        )
    return value


def _verdict(path: str, frontmatter: dict[str, Any], attempt: int) -> str | None:
    verdicts = frontmatter.get("verdict")
    value = verdicts.get(f"attempt_{attempt}") if isinstance(verdicts, dict) else None
    if value not in _VERDICTS:
        raise OperationRecordUnavailableError(
            f"беклог операции {path}: verdict.attempt_{attempt} должен быть success, failure "
            f"или null, получено {value!r}"
        )
    return value


def _trail(path: str, frontmatter: dict[str, Any]) -> dict[int, str]:
    trail = frontmatter.get("trail")
    if trail is None:
        return {}
    if not isinstance(trail, dict):
        raise OperationRecordUnavailableError(f"беклог операции {path}: trail не отображение")
    directories: dict[int, str] = {}
    for attempt in ATTEMPTS:
        value = trail.get(f"attempt_{attempt}")
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise OperationRecordUnavailableError(
                f"беклог операции {path}: trail.attempt_{attempt} должен быть путём каталога"
            )
        directories[attempt] = value
    return directories
