#!/usr/bin/env python3
"""Обёртка формальной проверки критериев BR (change add-formal-validation).

Валидирует ввод и исполняет ядро проверки в контейнере workspace-formal:1 —
образ собирается задачей mise formal-image (SPOT из apt-репозитория LRDE,
z3-solver из PyPI). Обёртка зависит только от стандартной библиотеки и docker;
контейнер запускается с --network none — прогон офлайн по построению.

Вызов:
  python3 -I tools/reqlint/formal.py docs/requirements/BR-001.md

Коды возврата: 0 — отчёт построен; 2 — ошибка ввода или окружения.
"""
import os
import subprocess
import sys

IMAGE = os.environ.get("FORMAL_IMAGE", "workspace-formal:1")

USAGE = "вызов: python3 -I tools/reqlint/formal.py <путь к карточке BR>"


def fail(message: str):
    print(f"formal: {message}", file=sys.stderr)
    sys.exit(2)


def main():
    if len(sys.argv) != 2:
        fail(USAGE)
    card = sys.argv[1]
    if not os.path.isfile(card):
        fail(f"карточка не найдена: {card}")
    root = os.getcwd()
    card_rel = os.path.relpath(os.path.abspath(card), root)
    if card_rel.startswith(".."):
        fail("карточка вне рабочего каталога — запустите из корня репозитория")
    cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{root}:/work", "-w", "/work", IMAGE,
        "python3", "-I", "/work/tools/reqlint/formal_core.py", card_rel,
    ]
    result = subprocess.run(cmd)
    if result.returncode not in (0, 2):
        fail(f"контейнер вернул код {result.returncode}; образ собран? — mise run formal-image")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
