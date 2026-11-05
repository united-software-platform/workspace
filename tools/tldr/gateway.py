"""Шлюз сканирования tldr: запуск scan.sh над сторонним проектом по файлу запроса.

Вызывается на хосте целью `make tldr-scan-ext`, которую раннер исполняет по запросу агента.
Параметры приходят файлом `.tldr/scan-request.json`, исход уходит файлом `.tldr/scan-result.json`:
`make` и клиент раннера искажают код возврата, поэтому истинный код исхода — только в файле
результата.

Коды исхода: `0` — сканирование выполнено (включая частичные сбои команд tldr: их итог —
в `stdout` и `exit_code` внутри файла результата), `1` — не удалось запустить `scan.sh`,
`2` — шлюз отказал, не запуская сканирование: нет файла запроса, запрос неверен, путь вне
разрешённых корней `TLDR_SCAN_ROOTS` или корни не заданы.

Скрипт использует только стандартную библиотеку: на хосте нет окружения проекта, есть лишь
`python3`, который уже нужен раннеру.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUEST_PATH = PurePosixPath(".tldr/scan-request.json")
RESULT_PATH = PurePosixPath(".tldr/scan-result.json")
EXCHANGE_IGNORE = PurePosixPath(".tldr/.gitignore")
# Тот же текст пишет клиент перед файлом запроса: файлы обмена скрыты от git в любом проекте,
# а `.gitignore` корня проекта не правится
EXCHANGE_IGNORE_TEXT = "# Файлы обмена со шлюзом tldr: локальные, не коммитятся\n*\n"

SCAN_SCRIPT = PurePosixPath("tools/tldr/scan.sh")

REQUIRED_FIELDS = frozenset({"request_id", "project", "report_name"})
OPTIONAL_FIELDS = frozenset({"ext", "exclude"})

EXT_PATTERN = r"^\.[A-Za-z0-9]+$"
EXCLUDE_PATTERN = r"^[A-Za-z0-9._/-]+(,[A-Za-z0-9._/-]+)*$"

SUCCESS = 0
SCAN_FAILURE = 1
REFUSED = 2


class RefusalError(Exception):
    """Отказ шлюза до запуска сканирования: исход с кодом `2`."""


@dataclass(frozen=True)
class Request:
    """Разобранный файл запроса."""

    request_id: str
    project: Path
    report_name: str
    ext: str | None
    exclude: str | None


@dataclass(frozen=True)
class Result:
    """Исход шлюза в составе файла результата."""

    request_id: str | None
    exit_code: int
    stdout: str
    stderr: str

    def to_json(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def request_id_of(raw: str) -> str | None:
    """Идентификатор запроса, если его удаётся достать даже из некорректного запроса."""
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if isinstance(payload, dict):
        value = payload.get("request_id")
        if isinstance(value, str) and value:
            return value
    return None


def parse_request(raw: str) -> Request:
    """Разобрать файл запроса и проверить его состав."""
    try:
        payload = json.loads(raw)
    except ValueError as error:
        raise RefusalError(f"файл запроса не является JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RefusalError("файл запроса должен содержать JSON-объект")

    expected = REQUIRED_FIELDS | OPTIONAL_FIELDS
    missing = sorted(REQUIRED_FIELDS - payload.keys())
    if missing:
        raise RefusalError(f"в запросе нет полей: {', '.join(missing)}")
    unexpected = sorted(payload.keys() - expected)
    if unexpected:
        raise RefusalError(f"в запросе лишние поля: {', '.join(unexpected)}")

    return Request(
        request_id=_text(payload, "request_id"),
        project=_absolute(payload["project"]),
        report_name=_name(payload["report_name"]),
        ext=_ext(payload.get("ext")),
        exclude=_exclude(payload.get("exclude")),
    )


def _text(payload: Mapping[str, Any], field: str) -> str:
    value = payload[field]
    if not isinstance(value, str) or not value:
        raise RefusalError(f"поле {field} должно быть непустой строкой")
    return value


def _absolute(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise RefusalError(f"поле project должно быть непустой строкой: {value!r}")
    path = Path(value)
    if not path.is_absolute():
        raise RefusalError(f"поле project должно быть абсолютным путём: {value}")
    return path


def _name(value: Any) -> str:
    name = _raw_name(value)
    if name in {".", ".."} or PurePosixPath(name).is_absolute() or "/" in name:
        raise RefusalError(f"поле report_name должно быть именем каталога: {name!r}")
    return name


def _raw_name(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise RefusalError(f"поле report_name должно быть непустой строкой: {value!r}")
    return value


def _ext(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RefusalError(f"поле ext должно быть расширением с ведущей точкой: {value!r}")
    if not re.fullmatch(EXT_PATTERN, value):
        raise RefusalError(f"поле ext должно быть расширением с ведущей точкой: {value!r}")
    return value


def _exclude(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RefusalError(f"поле exclude должно быть списком каталогов через запятую: {value!r}")
    if not re.fullmatch(EXCLUDE_PATTERN, value):
        raise RefusalError(
            f"поле exclude должно быть списком каталогов от корня через запятую, без пробелов: {value!r}"
        )
    return value


def parse_roots(value: str | None) -> list[Path]:
    """Разобрать `TLDR_SCAN_ROOTS`: абсолютные пути через запятую. Пусто — внешние запрещены."""
    entries = [entry.strip() for entry in (value or "").split(",") if entry.strip()]
    if not entries:
        raise RefusalError("TLDR_SCAN_ROOTS пуста: внешние сканирования запрещены")
    roots = []
    for entry in entries:
        path = Path(entry)
        if not path.is_absolute():
            raise RefusalError(f"корень TLDR_SCAN_ROOTS должен быть абсолютным путём: {entry}")
        roots.append(path)
    return roots


def check_project(request: Request, roots: Sequence[Path]) -> None:
    """Путь проекта обязан существовать каталогом и лежать внутри одного из корней.

    Проверяется после нормализации симлинков: путь, пришедший через символическую ссылку
    внутрь корня, но ведущую наружу, обязан остаться снаружи.
    """
    resolved = request.project.resolve()
    if not resolved.is_dir():
        raise RefusalError(f"каталог проекта не найден: {request.project}")
    for root in roots:
        base = root.resolve()
        if resolved == base or resolved.is_relative_to(base):
            return
    listed = ", ".join(str(root) for root in roots)
    raise RefusalError(f"путь {request.project} вне разрешённых корней TLDR_SCAN_ROOTS: {listed}")


def build_command(request: Request) -> list[str]:
    """Команда запуска scan.sh: путь проекта и каталог отчётов в корне этого проекта."""
    return ["sh", str(PROJECT_ROOT / SCAN_SCRIPT), str(request.project), f"reports/{request.report_name}"]


def scan_environment(request: Request, env: Mapping[str, str]) -> dict[str, str]:
    """Окружение scan.sh: настройки запроса перекрывают общие TLDR_* из окружения."""
    variables = dict(env)
    variables["TLDR_IMAGE"] = env.get("TLDR_IMAGE", "")
    if request.ext is not None:
        variables["EXT"] = request.ext
    if request.exclude is not None:
        variables["EXCLUDE"] = request.exclude.replace(",", " ")
    return variables


def execute(
    root: Path,
    env: Mapping[str, str],
    runner=subprocess.run,  # type: ignore[assignment]
) -> Result:
    """Выполнить запрос: удалить прежний результат, проверить запрос, запустить сканирование."""
    result_path = root / RESULT_PATH
    result_path.unlink(missing_ok=True)

    raw = _read_request(root)
    request_id = request_id_of(raw) if raw is not None else None
    try:
        if raw is None:
            raise RefusalError(f"нет файла запроса {REQUEST_PATH}")
        request = parse_request(raw)
        check_project(request, parse_roots(env.get("TLDR_SCAN_ROOTS")))
    except RefusalError as refusal:
        return Result(request_id, REFUSED, "", f"gateway: {refusal}")

    command = build_command(request)
    process_env = scan_environment(request, env)
    try:
        completed = runner(
            command,
            cwd=str(root),
            env=process_env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return Result(
            request_id, REFUSED, "", f"gateway: не удалось запустить scan.sh: {error}"
        )
    exit_code = SUCCESS if completed.returncode == 0 else SCAN_FAILURE
    return Result(request_id, exit_code, completed.stdout, completed.stderr)


def _read_request(root: Path) -> str | None:
    try:
        return (root / REQUEST_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def write_result(root: Path, result: Result) -> None:
    """Записать файл результата целиком: читатель не увидит его недописанным."""
    path = root / RESULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    ignore = root / EXCHANGE_IGNORE
    if not ignore.exists():
        ignore.write_text(EXCHANGE_IGNORE_TEXT, encoding="utf-8")
    draft = path.with_name(path.name + ".tmp")
    draft.write_text(json.dumps(result.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(draft, path)


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа: `gateway.py`."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        print(f"gateway.py не принимает аргументов: {args}", file=sys.stderr)
        return REFUSED
    result = execute(PROJECT_ROOT, os.environ)
    write_result(PROJECT_ROOT, result)
    if result.stderr:
        sys.stderr.write(result.stderr if result.stderr.endswith("\n") else result.stderr + "\n")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())