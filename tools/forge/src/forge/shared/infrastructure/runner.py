"""Раннер на хосте: настройки из окружения и вызов цели `make` по HTTP."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from forge.shared.application.settings import RunnerUnavailableError, SettingsUnavailableError

DEFAULT_TIMEOUT = 900.0


@dataclass(frozen=True)
class RunnerSettings:
    """Адрес и токен раннера, предел ожидания одной цели в секундах."""

    url: str
    token: str
    timeout: float = DEFAULT_TIMEOUT


RunnerCall = Callable[[RunnerSettings, str], None]


def call_runner(settings: RunnerSettings, target: str) -> None:
    """Вызвать цель раннера и дождаться её завершения; сбой — `RunnerUnavailableError`."""
    request = urllib.request.Request(
        f"{settings.url.rstrip('/')}/run/{target}", headers={"X-Runner-Token": settings.token}
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.timeout) as response:
            response.read()
    except urllib.error.HTTPError as error:
        raise RunnerUnavailableError(f"раннер отклонил цель {target}: HTTP {error.code}") from None
    except (urllib.error.URLError, OSError) as error:
        raise RunnerUnavailableError(f"раннер {settings.url} недоступен: {error}") from None


def runner_settings(environment: Mapping[str, str]) -> RunnerSettings | None:
    """Настройки раннера из `AGENT_RUNNER_*`; `None`, если адрес или токен не заданы."""
    url = environment.get("AGENT_RUNNER_URL", "")
    token = environment.get("AGENT_RUNNER_TOKEN", "")
    if not url or not token:
        return None
    timeout = environment.get("AGENT_RUNNER_TIMEOUT", "")
    try:
        return RunnerSettings(url, token, float(timeout) if timeout else DEFAULT_TIMEOUT)
    except ValueError:
        raise SettingsUnavailableError(
            f"AGENT_RUNNER_TIMEOUT должен быть числом секунд: {timeout!r}"
        ) from None
