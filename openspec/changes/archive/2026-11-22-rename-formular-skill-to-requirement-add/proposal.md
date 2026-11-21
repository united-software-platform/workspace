# Proposal

## Why

`formular` — имя плагина исполняемого беклога (провайдер `/backlog:backlog-generate`,
`/backlog:backlog-run`, `/backlog:backlog-template`), а не имя того, что делает операция:
при создании WRSP-032 имя плагина просочилось в имя навыка, операции и шаблона. Операции
`workflow` и `classify` работают на том же плагине и его имени не заимствуют; задвоение
нарушает терминологическую однозначность (TERM-002: одно имя — одно понятие). Владелец
переименовал навык в `requirement-add` и шаблон тоже: имя файла шаблона — ключ операции
беклог-плагина (`backlog generate --operation <имя>` читает `templates/<имя>.md`), поэтому
вместе со шаблоном переименовывается операция, а за операцией по конвенции репозитория —
capability; имя `formular` возвращается плагину как его единственное значение.
Переименование заявлено сразу после коммита `fa8bac7` (WRSP-032) — вызовов старого имени вне
репозитория ещё нет, миграция дешевле сейчас.

## What Changes

- **Навык**: `formular` → `requirement-add` — каталоги `.claude/skills/requirement-add/`
  и `.zcode/skills/requirement-add/`, внутри SKILL.md обновлены имя, заголовок,
  самоназывания; строка таблицы версий.
- **Операция и шаблон**: `templates/formular.md` → `templates/requirement-add.md`;
  порождение — `backlog generate --operation requirement-add`; новые прогоны ложатся
  в `backlog/requirement-add/<предмет>/`. Содержание шаблона не меняется — имя операции
  в нём несёт подстановка `{{operation}}`.
- **Capability**: `formular-operation` → `requirement-add-operation` — дельта снимает все
  требования старой capability (REMOVED с Reason/Migration) и заводит новую с теми же
  требованиями под обновлёнными именами и текстами.
- **Живые ссылки** на операцию обновляются: docstring `tools/reqlint/reqlint.py`, заголовок
  `tools/reqlint/rules.yml`.
- **Свидетельства истории не трогаются**: прогон `backlog/formular/20261121234009-past-work-search/`
  и формулировка «операцией formular» в `docs/requirements/BR-001.md` — факты прогона
  под старым именем; архив `add-formular-skill` — неизменная запись.

## Capabilities

### New Capabilities

- `requirement-add-operation`: операция беклога `requirement-add` и навык-обёртка
  `requirement-add` — формирование бизнес-требования прожаркой в карточку BR из девяти полей
  со стоп-знаком принятия и фиксацией артефактом `docs/requirements/<ID>.md`.

### Modified Capabilities

- `formular-operation`: все девять требований снимаются (REMOVED с Reason/Migration) —
  capability переименована в `requirement-add-operation` вместе с операцией; поведение
  требований сохранено в новой capability.

## Impact

- Правятся файлы: `.claude/skills/formular/SKILL.md` → `.claude/skills/requirement-add/SKILL.md`,
  `.zcode/skills/formular/SKILL.md` → `.zcode/skills/requirement-add/SKILL.md`,
  `templates/formular.md` → `templates/requirement-add.md` (перемещения + правка имён),
  `tools/reqlint/reqlint.py` и `tools/reqlint/rules.yml` (упоминания операции),
  `openspec/specs/formular-operation/` → `openspec/specs/requirement-add-operation/`
  (через дельту этого change при архивации).
- Не правятся: `backlog/formular/` (свидетельство прогона), `docs/requirements/BR-001.md`
  (историческая фиксация), `openspec/changes/archive/` (неизменная запись).
- Точка вызова меняется: `/requirement-add` вместо `/formular`; лётный change
  `add-multilevel-requirements-validation` перестраивается на новое имя и применяется
  после этого переименования.
