# Tasks

## 1. Снять копии поставки

- [x] 1.1 Пройти гейт редактирования (GIT-020): в `git status --porcelain` только неотслеживаемое (`??`), правок отслеживаемых файлов нет; при наличии — остановиться и спросить владельца
- [x] 1.2 Снять навыки и шаблоны: `git rm -r .claude/skills/project-docs .claude/skills/workflow-fast .claude/skills/workflow-grill` и `git rm templates/workflow.md templates/workflow-fast.md`. Проверка: `git status --short` называет 8 удалений
- [x] 1.3 Снять правила и точки входа: `git rm -r rules CLAUDE.md AGENTS.md`. Проверка: `git status --short` называет 10 удалений сверх задачи 1.2; `rules/`, `CLAUDE.md` и `AGENTS.md` в рабочем дереве нет
- [x] 1.4 Снять три повисшие локальные ссылки: `rm .zcode/skills/project-docs .zcode/skills/workflow-fast .zcode/skills/workflow-grill` (каталог в игноре, удаляются только ссылки). Проверка: `ls .zcode/skills` не называет эти три имени

## 2. Задача установки и её описание

- [x] 2.1 Добавить в `mise.toml` задачу `init-tessera` и включить её в `depends` задачи `init`; два комментария перевести на `.tessera/rules/environment.md`. Проверка: `mise tasks ls` называет `init-tessera`, `mise tasks info init` перечисляет её в зависимостях, `git grep -n 'rules/' -- mise.toml` находит только `.tessera/rules/`

  ```toml
  [tasks.init-tessera]
  description = "Установить поставку tessera в проект: навыки, правила, точку входа AGENTS.md"
  run = "curl -fsSL https://raw.githubusercontent.com/united-software-platform/tessera/main/scripts/install.sh | bash -s -- --project --profile full --rules all --yes"
  ```

- [x] 2.2 Дописать в `.gitignore`: `.agents/`, `.claude/skills/*` с явным разрешением 11 собственных навыков (`classify`, `classify-batch`, `classify-batch-enrich`, `domain-layout`, шесть `openspec-*`, `requirement-add`), `.tessera/registry.json`. Проверка: `git check-ignore -v .agents/skills/pr .claude/skills/pr .tessera/registry.json` называет все три пути, `git check-ignore .claude/skills/classify/SKILL.md` не называет ничего, `git status --porcelain` больше не показывает `.agents/` и ссылки в `.claude/skills/`
- [x] 2.3 Поправить `README.md`: в «Что нужно» добавить `bash`, `curl` и доступ к GitHub для скрипта поставки и `python3` для команды `backlog`; в шаге 2 написать, что `mise run init` ставит и поставку tessera; в «Ограничения» добавить незакреплённость версий источников и условие чтения `AGENTS.md` в Claude Code (версия 2.1.277 и новее, нет `CLAUDE.md` в проекте и выше него). Проверка: `grep -n 'rules/' README.md` пусто, команда шага 2 исполняется в задаче 3.1

## 3. Установка поставки

- [x] 3.1 Выполнить `mise run init-tessera` из корня репозитория. Установщик также перезаписывает лаунчер `~/.local/bin/backlog` вне репозитория тем же содержимым. При отказе установщика — остановиться и показать отказ владельцу; возвращать файлы из git только по его явному запросу (GIT-018). Проверка: отчёт установщика называет самопроверку пройденной, неисправных ссылок 0, секцию правил `AGENTS.md` — «записана»
- [x] 3.2 Сверить размещение. Проверка: `curl -fsSL https://raw.githubusercontent.com/united-software-platform/tessera/main/scripts/install.sh | bash -s -- --registry --project` даёт `"mode": "project"` и `status: complete` у навыков и правил; `ls .tessera/rules` называет 8 файлов; `project-docs`, `workflow-fast` и `workflow-grill` в `.agents/skills/` и `.claude/skills/` — ссылки в `~/.local/share/tessera/`; `AGENTS.md` начинается с `# workspace` и несёт одну секцию `## Правила tessera`

## 4. Ссылки репозитория

- [x] 4.1 Поправить `CONTRIBUTING.md`: «Правила репозитория» — `.tessera/rules/`; «Точки входа агентов» — `AGENTS.md`, его создаёт установщик tessera; строку «Навыки-обёртки операций» заменить описанием собственных навыков проекта и навыков поставки; семь ссылок таблицы норм перевести на `./.tessera/rules/`; дописать строку версии. Проверка: каждая ссылка таблицы норм ведёт в существующий файл, новая строка версии — последняя в таблице
- [x] 4.2 Поправить `GLOSSARY.md`: ссылку на правила DDD перевести на `./.tessera/rules/ddd.md`, дописать строку версии. Проверка: `git grep -n 'rules/' -- GLOSSARY.md` называет только `.tessera/rules/`, новая строка версии — последняя в таблице
- [x] 4.3 Проверить ссылки по репозиторию. Проверка: `git grep -n -P '(?<!\.tessera)/rules/|(^|[^/.A-Za-z0-9_-])rules/' -- . ':(exclude)backlog' ':(exclude)openspec/changes' ':(exclude)docs/archive' ':(exclude).tessera'` пусто

## 5. Итоговые проверки

- [x] 5.1 Сверить состав git. Проверка: `git status --porcelain` называет 18 удалений, правки `mise.toml`, `.gitignore`, `README.md`, `CONTRIBUTING.md`, `GLOSSARY.md`, новые `AGENTS.md` и 8 файлов `.tessera/rules/` — и не называет `.agents/`, ссылки навыков и `.tessera/registry.json`
- [x] 5.2 Проверить идемпотентность: повторный `mise run init-tessera`. Проверка: `git status --porcelain` до и после запуска одинаков
- [x] 5.3 Проверить согласованность спецификаций. Проверка: `openspec validate --all` — расхождений нет
- [x] 5.4 Хостовая проверка владельца: перезапустить сессию харнеса. Проверка: навыки `workflow-fast`, `workflow-grill` и `project-docs` доступны из каталогов навыков проекта и не разрешаются в `.zcode/skills/`; `AGENTS.md` в контексте агента — файл установщика

## Workflow follow-up

- Коммит — по отдельному запросу владельца (GIT-015), заголовок `WRSP-039: подключить фреймворк tessera`.
- Архивировать изменение после приёмки, синхронизировав спеки `agent-tools-supply` и `dev-workflow`.
- Отметить пункты «Готово, когда» в issue #34.
