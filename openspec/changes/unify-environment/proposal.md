# Proposal

## Why

Репозиторий workspace становится зонтичным для дочерних проектов и должен гибко поставлять им
инфраструктуру. Сегодняшнее окружение — точечный набор без зафиксированного стандарта: docker
compose с контейнерной поставкой dev-набора (sdd-kit), forge, Makefile — оно не масштабируется
на поставку и не даёт дочернему проекту механического способа подключиться.

## What Changes

- **BREAKING** Контейнерная поставка dev-набора sdd-kit исключена: образы `sdd-developer-kit`
  и `codex-box`, сервисы `claude`/`codex`, `docker-compose.yml`, раннер `tools/host-runner/`,
  `tools/make-lint/`, манифест `.sdd-kit-manifest.json`. Харнессы (claude, codex, dsh) — выбор
  пользователя, не поставка.
- **BREAKING** Forge отключён целиком: `docker/`, `tools/forge-env/`, `tools/liquibase/`,
  `tools/forge/`, шаблоны `templates/forge-*.md`, навык `.claude/skills/forge/`, манифест
  `.forge-manifest.json`.
- **BREAKING** `Makefile` удаляется; задачи окружения переезжают в mise (`mise run`):
  init-env, init-dirs, init-gitignore, init-ssh-key, init-ssh-config, openspec-init, tldr-scan,
  tldr-scan-ext.
- Закрепляется единый стандарт окружения: mise — инструментарий (`node`, `python`,
  `npm:@openspec/cli`); k3s — сервисы (helm — единица поставки, одноразовые прогоны — Jobs,
  доступ — `kubectl port-forward`, публикация портов не используется).
- Паттерн переменных: несекретные значения — `[env]` в `mise.toml`, секреты — git-ignored
  `.env`, подключаемый mise; `.env.example` сокращается до tldr и embeddings-переменных.
- tldr-сканирование исполняется Job'ом в k3s; контракт скрипта и шлюза сохраняется.
- Правила: добавлен `rules/environment.md`; `rules/makefile-rules.md` и `rules/docker.md`
  исключены из поставки и перечней `CLAUDE.md`/`AGENTS.md`.
- `README.md` переписан под новый стандарт: предусловия, шаги, ограничения.

## Capabilities

### New Capabilities

- `environment`: единый стандарт окружения зонтичного репозитория — границы mise и k3s,
  паттерн переменных, задачи mise, отказ от публикации портов и харнессов.

### Modified Capabilities

- `code-scan`: запуск сканирования переходит с make-целей и docker-механики на задачи mise
  и Job в k3s; требования про раннер и встраивание блоками в файлы kit'а снимаются.

## Impact

Удаляемые: `Makefile`, `docker-compose.yml`, `docker/`, `tools/make-lint/`, `tools/host-runner/`,
`tools/forge-env/`, `tools/forge/`, `tools/liquibase/`, `templates/forge-model.md`,
`templates/forge-seed.md`, `templates/forge-seed-apply.md`, `templates/forge-apply.md`,
`.claude/skills/forge/`, `.sdd-kit-manifest.json`, `.forge-manifest.json`, `rules/makefile-rules.md`,
`rules/docker.md`.

Правимые: `mise.toml`, `.env.example`, `.gitignore`, `CLAUDE.md`, `AGENTS.md`, `README.md`,
`tools/tldr/scan.sh`, `tools/tldr/gateway.py`, `tools/tldr/README.md`, `openspec/specs/code-scan/`.

Новые: `rules/environment.md`, `openspec/changes/unify-environment/`.
