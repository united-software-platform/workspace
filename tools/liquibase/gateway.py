"""Шлюз Liquibase: накат и откат changelog в контейнере `lbfr-liquibase` по файлу запроса.

Вызывается на хосте рецептами `make liquibase-update` и `make liquibase-rollback`, которые
раннер исполняет по запросу агента. Параметры приходят файлом `.forge/liquibase-request.json`,
исход уходит файлом `.forge/liquibase-result.json`: `make` и клиент раннера искажают код
возврата, поэтому истинный код исхода — только в файле результата.

Коды исхода: `0` — Liquibase выполнил команду, `1` — Liquibase завершился ошибкой,
`2` — шлюз отказал, не запуская Liquibase.

Скрипт использует только стандартную библиотеку: на хосте нет окружения проекта, есть лишь
`python3`, который уже нужен раннеру.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUEST_PATH = PurePosixPath(".forge/liquibase-request.json")
RESULT_PATH = PurePosixPath(".forge/liquibase-result.json")
EXCHANGE_IGNORE = PurePosixPath(".forge/.gitignore")
# Тот же текст пишет forge перед файлом запроса: файлы обмена скрыты от git в любом проекте,
# а `.gitignore` корня проекта не правится
EXCHANGE_IGNORE_TEXT = "# Файлы обмена forge со шлюзом Liquibase: локальные, не коммитятся\n*\n"

SERVICE = "lbfr-liquibase"
ACTIONS = ("update", "rollback")

SUCCESS = 0
LIQUIBASE_FAILURE = 1
REFUSED = 2

# Адрес и учётные данные целевой БД передаются Liquibase переменными окружения
LIQUIBASE_VARIABLES = (
    "LIQUIBASE_COMMAND_URL",
    "LIQUIBASE_COMMAND_USERNAME",
    "LIQUIBASE_COMMAND_PASSWORD",
)

_REQUIRED_FIELDS = frozenset({"request_id", "action", "changelog", "host", "port", "database"})
_ROLLBACK_FIELD = "count"


class RefusalError(Exception):
    """Отказ шлюза до запуска Liquibase: исход с кодом `2`."""


@dataclass(frozen=True)
class Request:
    """Разобранный файл запроса."""

    request_id: str
    action: str
    changelog: str
    host: str
    port: int
    database: str
    count: int | None


@dataclass(frozen=True)
class Credentials:
    """Учётные данные целевой БД, взятые из окружения хоста."""

    user: str
    password: str


@dataclass(frozen=True)
class AllowedDatabase:
    """Запись перечня тестовых БД: `None` вместо имени разрешает любую БД сервера."""

    host: str
    port: int
    database: str | None

    def admits(self, host: str, port: int, database: str) -> bool:
        return (
            self.host == host
            and self.port == port
            and (self.database is None or self.database == database)
        )


@dataclass(frozen=True)
class Result:
    """Исход шлюза в составе файла результата."""

    request_id: str | None
    action: str
    exit_code: int
    stdout: str
    stderr: str

    def to_json(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action,
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

    action = payload.get("action")
    if action not in ACTIONS:
        raise RefusalError(f"действие должно быть одним из {', '.join(ACTIONS)}: {action!r}")
    expected = _REQUIRED_FIELDS | {_ROLLBACK_FIELD} if action == "rollback" else _REQUIRED_FIELDS
    missing = sorted(expected - payload.keys())
    if missing:
        raise RefusalError(f"в запросе нет полей: {', '.join(missing)}")
    unexpected = sorted(payload.keys() - expected)
    if unexpected:
        raise RefusalError(f"в запросе лишние поля: {', '.join(unexpected)}")

    return Request(
        request_id=_text(payload, "request_id"),
        action=action,
        changelog=_text(payload, "changelog"),
        host=_text(payload, "host"),
        port=_port(payload["port"]),
        database=_text(payload, "database"),
        count=_count(payload[_ROLLBACK_FIELD]) if action == "rollback" else None,
    )


def _text(payload: Mapping[str, Any], field: str) -> str:
    value = payload[field]
    if not isinstance(value, str) or not value:
        raise RefusalError(f"поле {field} должно быть непустой строкой")
    return value


def _port(value: Any) -> int:
    if not _is_integer(value) or not 1 <= value <= 65535:
        raise RefusalError(f"поле port должно быть номером порта: {value!r}")
    return int(value)


def _count(value: Any) -> int:
    if not _is_integer(value) or value <= 0:
        raise RefusalError(f"поле count должно быть целым положительным числом: {value!r}")
    return int(value)


def _is_integer(value: Any) -> bool:
    # bool — подкласс int в Python, но true в поле числа — ошибка запроса, а не единица
    return isinstance(value, int) and not isinstance(value, bool)


def check_action(request: Request, action: str) -> None:
    """Действие цели `make` должно совпадать с действием в файле запроса."""
    if request.action != action:
        raise RefusalError(
            f"цель вызвана для действия {action}, а в запросе действие {request.action}"
        )


def resolve_changelog(root: Path, changelog: str) -> str:
    """Проверить путь changelog и вернуть его нормализованным относительно корня проекта."""
    if PurePosixPath(changelog).is_absolute() or Path(changelog).is_absolute():
        raise RefusalError(f"путь changelog должен быть относительным: {changelog}")
    base = root.resolve()
    target = (base / changelog).resolve()
    if not target.is_relative_to(base):
        raise RefusalError(f"путь changelog выходит за корень проекта: {changelog}")
    if not target.is_file():
        raise RefusalError(f"changelog не найден: {changelog}")
    return target.relative_to(base).as_posix()


def parse_allowlist(value: str | None) -> list[AllowedDatabase]:
    """Разобрать `FORGE_TEST_DB_ALLOWLIST`: записи `хост:порт/имя` через запятую."""
    entries = [entry.strip() for entry in (value or "").split(",") if entry.strip()]
    if not entries:
        raise RefusalError(
            "перечень тестовых БД FORGE_TEST_DB_ALLOWLIST пуст: БД не считается тестовой"
        )
    return [_allowed_database(entry) for entry in entries]


def _allowed_database(entry: str) -> AllowedDatabase:
    server, slash, database = entry.rpartition("/")
    host, colon, port = server.rpartition(":")
    if not (slash and colon and host and database and port.isdigit()):
        raise RefusalError(f"запись перечня тестовых БД не в формате хост:порт/имя: {entry}")
    return AllowedDatabase(host, int(port), None if database == "*" else database)


def check_allowlist(request: Request, allowlist: Sequence[AllowedDatabase]) -> None:
    """БД запроса должна совпасть хотя бы с одной записью перечня."""
    if not any(item.admits(request.host, request.port, request.database) for item in allowlist):
        raise RefusalError(
            f"БД вне перечня тестовых: {request.host}:{request.port}/{request.database}"
        )


def select_credentials(request: Request, env: Mapping[str, str]) -> Credentials:
    """Выбрать учётные данные по хосту запроса: сервер тестов или целевая БД операций."""
    for prefix in ("FORGE_TEST_DB", "FORGE_DB"):
        if env.get(f"{prefix}_HOST") != request.host:
            continue
        user = env.get(f"{prefix}_USER", "")
        password = env.get(f"{prefix}_PASSWORD", "")
        if not user or not password:
            raise RefusalError(f"в окружении хоста не заданы {prefix}_USER и {prefix}_PASSWORD")
        return Credentials(user, password)
    raise RefusalError(
        f"хост {request.host} не совпадает ни с FORGE_DB_HOST, ни с FORGE_TEST_DB_HOST"
    )


def build_command(request: Request, changelog: str) -> list[str]:
    """Команда запуска Liquibase. Учётные данные в неё не входят: они идут окружением."""
    liquibase = (
        ["update"] if request.action == "update" else ["rollback-count", f"--count={request.count}"]
    )
    command = ["docker", "compose", "run", "--rm", "-T"]
    # `-e ИМЯ` без значения берёт значение из окружения docker compose: пароль не попадает
    # в аргументы процесса, видимые в списке процессов хоста
    for name in LIQUIBASE_VARIABLES:
        command += ["-e", name]
    # Путь относительный: точка входа образа переходит в /liquibase/changelog, куда смонтирован
    # проект, и ставит --search-path=.
    return [*command, SERVICE, *liquibase, f"--changelog-file={changelog}"]


def liquibase_environment(request: Request, credentials: Credentials) -> dict[str, str]:
    """Переменные Liquibase с адресом и учётными данными целевой БД."""
    url = f"jdbc:postgresql://{request.host}:{request.port}/{request.database}"
    return dict(
        zip(LIQUIBASE_VARIABLES, (url, credentials.user, credentials.password), strict=True)
    )


Runner = Callable[[list[str], Path, dict[str, str]], "subprocess.CompletedProcess[str]"]


def run_process(
    command: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Запустить команду и собрать её вывод."""
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def execute(
    action: str,
    root: Path,
    env: Mapping[str, str],
    runner: Runner = run_process,
) -> Result:
    """Выполнить запрос: удалить прежний результат, проверить запрос, запустить Liquibase."""
    result_path = root / RESULT_PATH
    result_path.unlink(missing_ok=True)

    raw = _read_request(root)
    request_id = request_id_of(raw) if raw is not None else None
    try:
        if raw is None:
            raise RefusalError(f"нет файла запроса {REQUEST_PATH}")
        if action not in ACTIONS:
            raise RefusalError(f"неизвестное действие цели: {action}")
        request = parse_request(raw)
        check_action(request, action)
        changelog = resolve_changelog(root, request.changelog)
        check_allowlist(request, parse_allowlist(env.get("FORGE_TEST_DB_ALLOWLIST")))
        credentials = select_credentials(request, env)
    except RefusalError as refusal:
        return Result(request_id, action, REFUSED, "", f"gateway: {refusal}")

    process_env = {**env, **liquibase_environment(request, credentials)}
    try:
        completed = runner(build_command(request, changelog), root, process_env)
    except OSError as error:
        return Result(
            request_id, action, REFUSED, "", f"gateway: не удалось запустить docker: {error}"
        )
    exit_code = SUCCESS if completed.returncode == 0 else LIQUIBASE_FAILURE
    return Result(request_id, action, exit_code, completed.stdout, completed.stderr)


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
    """Точка входа: `gateway.py <update|rollback>`."""
    args = list(sys.argv[1:] if argv is None else argv)
    action = args[0] if len(args) == 1 else ""
    result = execute(action, PROJECT_ROOT, os.environ)
    write_result(PROJECT_ROOT, result)
    if result.stderr:
        sys.stderr.write(result.stderr if result.stderr.endswith("\n") else result.stderr + "\n")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
