# Proposal

## Why

Классификация проекта сегодня — одиночный ручной прогон: владелец называет проект, выбирает источник из пяти результатов поиска и принимает классификацию на стоп-знаках. Для сбора сведений о десятке проектов это десятки остановок и столько же запусков. Задача WRSP-026 требует пакетный прогон: список собирается одним опросом, классификация идёт в фоне без остановок.

## What Changes

- Добавляется навык `classify-batch`: опрос владельца до полного принятия списка проектов, запуск параллельных фоновых агентов на модели haiku (по одному на проект), сводный отчёт по автоматическим выборам.
- Добавляется шаблон операции `templates/classify-project-auto.md`: автоматический вариант классификации проекта — без маркеров «Стоп-знак.», решения фиксируются исполнителем-автоматом с записью авторства во фронтматтер.
- Утилита классификации вызывается напрямую (`uv run classifier`); вложенный беклог `classify` не порождается, режим авто его спеки не затрагивает.
- Итог прогона — один файл `projects/{YYYYMMDDHHMMSS}.json` на пакет; карточки прогона — `projects/{штамп}.cards/item-NN.json`.
- `.gitignore` дополняется записями `/backlog/classify-project-auto/` и `/projects/` (блок `domain-classifier`).
- Ручной шаблон `templates/classify-project.md` и операция `classify` не меняются — живут параллельно для одиночных прогонов с живыми стоп-знаками.

## Capabilities

### New Capabilities

- `batch-project-classification`: пакетная классификация проектов — опрос до принятия списка, фоновые агенты-исполнители на haiku, автоматическое закрытие точек решений с фиксацией авторства, итоговый JSON прогона, устойчивость к падению отдельных проектов.

### Modified Capabilities

— (нет): требование ручных операций `classify` и `classify-project` не меняется, утилита классификации не меняется.

## Impact

- Новые файлы: `.claude/skills/classify-batch/SKILL.md`, `templates/classify-project-auto.md`.
- Правка `.gitignore` — две записи в блок `domain-classifier`.
- Зависимости: утилита `tools/classifier/` (вызов без изменений), переменные окружения `WEBSEARCH_*` (поиск) и `EMBEDDINGS_*` (классификация), навыки плагина backlog `/backlog:backlog-generate` и `/backlog:backlog-run`.
- Репозиторий: `united-software-platform/workspace`, задача [WRSP-026](https://github.com/united-software-platform/workspace/issues/16), ветка `feature/wrsp-026-batch-project-classification`.
