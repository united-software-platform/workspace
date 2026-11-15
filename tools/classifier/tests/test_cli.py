"""Интеграционные тесты CLI: успех, needs_confirmation, ошибка входа.

Прогоны идут на CLASSIFIER_EMBEDDINGS=stub — детерминированный фейк, сети нет.
Порог needs_confirmation в stub-режиме проверяется через высокий порог CLI.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CARD = {
    "name": "novamart-checkout",
    "purpose": "Сервис оформления заказа магазина: корзина, оплата",
    "facets": {"domains": ["ecommerce"]},
}


def _run(card_file: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, CLASSIFIER_EMBEDDINGS="stub")
    for name in ("EMBEDDINGS_BASE_URL", "EMBEDDINGS_API_KEY", "EMBEDDINGS_MODEL"):
        env.pop(name, None)
    return subprocess.run(
        [sys.executable, "-m", "classifier.cli.main", str(card_file), *extra],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
        env=env,
    )


def test_cli_success_code_zero_without_env_and_network(tmp_path: Path) -> None:
    # Переменные EMBEDDINGS_* сняты: CLI работает на stub, сети нет
    card_file = tmp_path / "card.json"
    card_file.write_text(json.dumps(CARD, ensure_ascii=False), encoding="utf-8")
    result = _run(card_file, "--threshold", "0.0")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["needs_confirmation"] is False
    assert payload["spcf"]["L1_application_domain"][0]["role"] == "primary"


def test_cli_needs_confirmation_code_one(tmp_path: Path) -> None:
    card_file = tmp_path / "card.json"
    card_file.write_text(json.dumps(CARD, ensure_ascii=False), encoding="utf-8")
    result = _run(card_file, "--threshold", "0.99")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["needs_confirmation"] is True
    assert payload["reasons"]


def test_cli_broken_card_code_two(tmp_path: Path) -> None:
    card_file = tmp_path / "card.json"
    card_file.write_text("{не json", encoding="utf-8")
    result = _run(card_file)
    assert result.returncode == 2
    assert "ошибка" in result.stderr


def test_cli_missing_card_code_two(tmp_path: Path) -> None:
    result = _run(tmp_path / "нет-такого.json")
    assert result.returncode == 2


def test_cli_missing_export_code_two(tmp_path: Path) -> None:
    card_file = tmp_path / "card.json"
    card_file.write_text(json.dumps(CARD, ensure_ascii=False), encoding="utf-8")
    result = _run(card_file, "--export-dir", str(tmp_path / "нет-выгрузки"))
    assert result.returncode == 2
    assert "выгрузки" in result.stderr


def test_cli_stub_is_deterministic(tmp_path: Path) -> None:
    # Два прогона на stub дают одинаковый контракт
    card_file = tmp_path / "card.json"
    card_file.write_text(json.dumps(CARD, ensure_ascii=False), encoding="utf-8")
    first = _run(card_file, "--threshold", "0.0").stdout
    second = _run(card_file, "--threshold", "0.0").stdout
    assert first == second
