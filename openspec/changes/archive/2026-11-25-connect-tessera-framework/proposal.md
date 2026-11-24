# Proposal

## Why

Инструменты рабочего процесса — правила, навыки и шаблоны операций — лежат в репозитории
копиями и одновременно входят в поставку фреймворка tessera. Копии стареют (навыки
`workflow-fast` и `workflow-grill` в репозитории — версии 1.0.1 и 1.0.2, в поставке — 1.1.0)
и правятся в двух местах, а перечень правил в `CLAUDE.md` дублирует `AGENTS.md` вручную.
Запрос владельца — WRSP-039: перенести рабочие процессы в tessera и убрать дублирование.

## What Changes

- Удалить из репозитория копии, входящие в поставку tessera: каталог `rules/` (8 правил),
  навыки `project-docs`, `workflow-fast`, `workflow-grill` в `.claude/skills/` и шаблоны
  операций `templates/workflow.md`, `templates/workflow-fast.md`.
- Ставить поставку tessera в проектном режиме задачей mise `init-tessera`, входящей
  в `mise run init`: навыки — ссылками в `.agents/skills/` и `.claude/skills/`, правила —
  копиями в `.tessera/rules/`.
- **BREAKING**: `CLAUDE.md` удаляется; `AGENTS.md` создаёт установщик и несёт только его
  содержание. Ручные разделы точки входа — напоминание о гейте чтения, напоминание
  `GIT-012`, таблица версий — уходят; сами нормы остаются в правилах.
- Копии правил `.tessera/rules/` коммитятся; ссылки навыков и `.tessera/registry.json`
  исключаются из git.
- Перевести ссылки репозитория с `rules/` на `.tessera/rules/`: `CONTRIBUTING.md`,
  `GLOSSARY.md`, комментарии `mise.toml`.
- Записать в спеке `dev-workflow` поведение обёртки поставки версии 1.1.0: проверку
  зависимостей и запасной шаблон плагина.

## Capabilities

### New Capabilities

- `agent-tools-supply`: поставка инструментов агента — правил и навыков — из фреймворка
  tessera. Покрывает единственный источник, установку в проект, состав git, точку входа
  агентов и пути ссылок на правила.

### Modified Capabilities

- `dev-workflow`: делегирование порождению передаёт каталог шаблонов — проекта или плагина
  tessera-plugin; контракт шаблона операции относится к обоим расположениям; добавлена
  проверка зависимостей обёртки.

## Impact

- Удаляется 18 отслеживаемых файлов: `rules/` (8), `.claude/skills/project-docs/` (4),
  `.claude/skills/workflow-fast/SKILL.md`, `.claude/skills/workflow-grill/SKILL.md`,
  `templates/workflow.md`, `templates/workflow-fast.md`, `CLAUDE.md`, `AGENTS.md`.
- Правятся `mise.toml` (задача `init-tessera`, два комментария), `.gitignore`,
  `CONTRIBUTING.md`, `GLOSSARY.md`, `README.md`.
- Установщик создаёт `AGENTS.md`, `.tessera/rules/` (8 копий), `.tessera/registry.json`
  и ссылки навыков в `.agents/skills/` и `.claude/skills/` (на момент сверки — по 34).
- Новые внешние зависимости: скрипт поставки tessera и три репозитория-источника (tessera,
  formular, mattpocock/skills). Ставятся веткой `main`, без закрепления версий.
- Claude Code читает `AGENTS.md` сам только с версии 2.1.277 и при отсутствии `CLAUDE.md`
  в каталогах проекта и выше него.
- Вне рамок: собственные навыки проекта (`classify`, `classify-batch`,
  `classify-batch-enrich`, `domain-layout`, `requirement-add`, `openspec-*`) и пять их
  шаблонов; пользовательские каталоги навыков и плагины харнесов; свидетельства прогонов
  в `backlog/`; правки в репозитории tessera.
