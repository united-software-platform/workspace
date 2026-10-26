"""Клиент шлюза Liquibase: файл запроса, вызов цели раннера, чтение файла результата.

Раннер на хосте исполняет цель `make liquibase-<действие>`, а шлюз пишет исход в файл:
код раннера и `make` истинного исхода не передают. Результат принимается, только если
его `request_id` совпадает с идентификатором текущего запроса.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from forge.migration.application.liquibase_gateway import GatewayResult, GatewayUnavailableError
from forge.shared.application.settings import RunnerUnavailableError
from forge.shared.domain.target_database import TargetDatabase
from forge.shared.infrastructure.runner import RunnerCall, RunnerSettings, call_runner

REQUEST_PATH = Path(".forge") / "liquibase-request.json"
RESULT_PATH = Path(".forge") / "liquibase-result.json"
EXCHANGE_IGNORE = Path(".forge") / ".gitignore"
# Тот же текст пишет шлюз на хосте: файлы обмена скрыты от git в любом проекте,
# а `.gitignore` корня проекта не правится
EXCHANGE_IGNORE_TEXT = "# Файлы обмена forge со шлюзом Liquibase: локальные, не коммитятся\n*\n"


class RunnerLiquibaseGateway:
    """Реализация контракта шлюза через файлы `.forge/` и раннер на хосте."""

    def __init__(
        self,
        project_root: Path,
        runner: RunnerSettings | None,
        call: RunnerCall = call_runner,
        new_request_id: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._root = project_root
        self._runner = runner
        self._call = call
        self._new_request_id = new_request_id

    def update(self, changelog: str, database: TargetDatabase) -> GatewayResult:
        return self._execute("update", changelog, database, {})

    def rollback(self, changelog: str, database: TargetDatabase, count: int) -> GatewayResult:
        return self._execute("rollback", changelog, database, {"count": count})

    def _execute(
        self, action: str, changelog: str, database: TargetDatabase, extra: dict[str, Any]
    ) -> GatewayResult:
        if self._runner is None:
            raise GatewayUnavailableError(
                "runner_unavailable",
                "раннер не настроен: не заданы AGENT_RUNNER_URL и AGENT_RUNNER_TOKEN",
            )
        request_id = self._new_request_id()
        request = {
            "request_id": request_id,
            "action": action,
            "changelog": self._relative(changelog),
            "host": database.host,
            "port": database.port,
            "database": database.name,
            **extra,
        }
        request_path = self._root / REQUEST_PATH
        request_path.parent.mkdir(parents=True, exist_ok=True)
        ignore = self._root / EXCHANGE_IGNORE
        if not ignore.exists():
            ignore.write_text(EXCHANGE_IGNORE_TEXT, encoding="utf-8")
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        try:
            self._call(self._runner, f"liquibase-{action}")
        except RunnerUnavailableError as error:
            raise GatewayUnavailableError("runner_unavailable", str(error)) from None
        return self._result(request_id)

    def _relative(self, changelog: str) -> str:
        path = Path(changelog)
        if path.is_absolute():
            root = self._root.resolve()
            resolved = path.resolve()
            if resolved.is_relative_to(root):
                return resolved.relative_to(root).as_posix()
        return path.as_posix()

    def _result(self, request_id: str) -> GatewayResult:
        path = self._root / RESULT_PATH
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise GatewayUnavailableError(
                "gateway_result_invalid",
                f"нет файла результата {RESULT_PATH}: цель не дошла до шлюза",
            ) from None
        except (OSError, ValueError) as error:
            raise GatewayUnavailableError(
                "gateway_result_invalid", f"файл результата {RESULT_PATH} не прочитать: {error}"
            ) from None
        if not isinstance(payload, dict) or payload.get("request_id") != request_id:
            raise GatewayUnavailableError(
                "gateway_result_invalid",
                f"файл результата {RESULT_PATH} относится к другому запросу",
            )
        exit_code = payload.get("exit_code")
        stdout, stderr = str(payload.get("stdout", "")), str(payload.get("stderr", ""))
        if exit_code == 2:
            raise GatewayUnavailableError("gateway_refused", stderr.strip() or "шлюз отказал")
        if exit_code not in (0, 1):
            raise GatewayUnavailableError(
                "gateway_result_invalid", f"неизвестный код исхода шлюза: {exit_code!r}"
            )
        return GatewayResult(request_id, int(exit_code), stdout, stderr)
