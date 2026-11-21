# Tasks

## 1. Навык

- [x] 1.1 Перенести каталоги навыка: `git mv .claude/skills/formular .claude/skills/requirement-add`
  и `mv .zcode/skills/formular .zcode/skills/requirement-add`. Проверка: оба новых пути
  существуют, старых каталогов нет
- [x] 1.2 Обновить SKILL.md под новое имя: frontmatter `name: requirement-add`, заголовок,
  самоназывания, «Вызвать /backlog:backlog-generate с операцией `requirement-add`», путь
  шаблона в разделе отказов `templates/requirement-add.md`; дописать строку версий 1.0.2
  (переименование по решению владельца). Проверка: `grep -ri formular` по SKILL.md пуст вне
  таблицы версий — исторические записи 1.0.0 и 1.0.2 упоминают прежнее имя правомерно;
  `diff` двух точек входа пуст

## 2. Операция и шаблон

- [x] 2.1 Перенести шаблон: `git mv templates/formular.md templates/requirement-add.md`;
  содержание не меняется — имя операции несёт подстановка `{{operation}}`. Проверка:
  `grep -i formular templates/requirement-add.md` пуст;
  `backlog check-template templates/requirement-add.md` — код возврата `0`
- [x] 2.2 Обновить живые ссылки на операцию: docstring `tools/reqlint/reqlint.py`
  («Вызов в операции formular» → «в операции requirement-add») и заголовок
  `tools/reqlint/rules.yml` («для операции formular» → «для операции requirement-add»).
  Проверка: `grep -ri formular tools/reqlint/` пуст

## 3. Интеграционная проверка

- [x] 3.1 Пройтись `grep -ri formular` по живым каталогам репозитория
  (`.claude/skills/`, `.zcode/skills/`, `templates/`, `tools/`, `docs/` без
  `docs/requirements/BR-001.md`): остаточных ссылок нет; упоминания остаются только
  в свидетельствах — `backlog/formular/`, BR-001, `docs/archive/`
  и `openspec/changes/archive/` — в исторических строках таблиц версий SKILL.md
  и в легитимных ссылках на сам плагин `formular/backlog` (упоминание движка, не операции)

## Workflow follow-up

- Применить change, затем архивировать; после архивации убедиться, что
  `openspec/specs/formular-operation/` исчез (пустой остаток удалить руками),
  а `openspec/specs/requirement-add-operation/` несёт девять требований.
- Переименование применяется раньше лётного `add-multilevel-requirements-validation` —
  тот перебазирован на новое имя и адресует `requirement-add-operation`.
