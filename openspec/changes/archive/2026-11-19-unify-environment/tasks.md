# Tasks

## 1. Вырезка

- [x] 1.1 Удалить `Makefile`, `docker-compose.yml`, `docker/`, `tools/make-lint/`, `tools/host-runner/` и манифест `.sdd-kit-manifest.json`; проверить `git status` — перечисленного в дереве нет
- [x] 1.2 Удалить forge-след: `tools/forge-env/`, `tools/forge/`, `tools/liquibase/`, `templates/forge-model.md`, `templates/forge-seed.md`, `templates/forge-seed-apply.md`, `templates/forge-apply.md`, `.claude/skills/forge/`, `.forge-manifest.json`; проверить `git status`
- [x] 1.3 Удалить `rules/makefile-rules.md` и `rules/docker.md`

## 2. Стандарт окружения

- [x] 2.1 Написать `rules/environment.md` по DOC-014/DOC-022: границы mise и k3s, паттерн переменных, задачи mise, доступ port-forward, харнессы вне поставки, ограничения (ENV-коды); проверить структуру файла
- [x] 2.2 Подключить `rules/environment.md` и снять `makefile-rules`/`docker` в перечнях `CLAUDE.md` и `AGENTS.md` синхронно (импорты и строки списка, записи таблиц версий)
- [x] 2.3 Наполнить `mise.toml`: инструменты `node`, `python`, `npm:@fission-ai/openspec`; секция `[env]` с `_.file = ".env"`; задачи init, init-env, init-dirs, init-gitignore, init-ssh-key, init-ssh-config, openspec-init, tldr-scan, tldr-scan-ext; проверено `mise tasks` (разбирается, 9 задач) и двойным прогоном `mise run init` (создаёт и пропускает идемпотентно)
- [x] 2.4 Сократить `.env.example` до git-блока и блока embeddings; вычистить блок `liquibase-forge` из `.gitignore`; проверено `git status -- .env.example .gitignore`

## 3. tldr в k3s

- [x] 3.1 Перевести `tools/tldr/scan.sh` с docker run на Job в k3s (hostPath readOnly + emptyDir Memory перекрытия + hostPath отчётов, ожидание Complete/Failed, kubectl logs, удаление Job'а); проверено `sh -n` и запуск без аргументов (код 2)
- [x] 3.2 Сверить `tools/tldr/gateway.py` с новым scan.sh: контракт вызова и коды возврата не менялись, обновлена докстринг; проверено `python3 -m py_compile`
- [x] 3.3 Обновить `tools/tldr/README.md` под запуск через mise и Job в k3s

## 4. Документы входа

- [x] 4.1 Переписать `README.md` по DGN-003: бейдж лицензии, «Что нужно» (mise, k3s, kubectl, helm), шаги установки и инициализации, «Куда дальше» (mise tasks, openspec list), «Ограничения» (нет бейджа версии — нет носителя; k3s — Linux-хост), «Лицензия»
- [x] 4.2 Прогнать `openspec validate unify-environment --strict` (valid); `sh -n` по scan.sh и `python3 -m py_compile` по шлюзу (чисто); итоговый `git status` сверен с перечнем Impact из proposal.md

## Workflow follow-up

- Полный прогон `mise run tldr-scan` — на хосте владельца с кластером k3s и kubectl: в среде исполнения ветки кластера нет.
- Archive изменения после приёмки ревью; затем коммит и PR по запросу владельца.
