"""Команды CLI `forge`: каждый модуль регистрирует одну команду и исполняет её.

Модуль команды объявляет `register(subparsers)`, которая добавляет подкоманду и задаёт ей
`handler` через `set_defaults`. Новая команда — новый модуль в `COMMANDS`, без правки
ветвлений в `main`.
"""

from __future__ import annotations

from forge.cli.commands import (
    abandon,
    apply,
    close,
    generate,
    generate_seed,
    reconcile,
    reconcile_seed,
    report,
    resume,
    rollback,
    status,
    stop,
    validate,
    validate_seed,
)

COMMANDS = (
    validate,
    validate_seed,
    generate,
    generate_seed,
    apply,
    reconcile,
    reconcile_seed,
    rollback,
    status,
    stop,
    resume,
    close,
    abandon,
    report,
)
