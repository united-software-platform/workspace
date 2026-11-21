# Tasks

## 1. Шаблон операции formular

- [x] 1.1 Написать `templates/formular.md` по грамматике `templates/workflow-fast.md`
  (решения 2–5 design.md): фронтматтер с подстановками `template_version`, `date`,
  `operation`, `subject`, `runner`, `requirement` (+ парные `*_scalar`), значения
  `br_card: null` и `confirmed.irreversible_step: null`; группы задач «1 Предусловия»
  (runner, lint), «2 Прожарка BR» (выявить требование, прожарка `/mattpocock-skills:grilling`
  по девяти полям, собрать `br_card` в статусе `Draft`), «3 Стоп-знак принятия»
  (`Proposed`/`Rejected`, фиксация вердикта), «4 Итог»; у каждой задачи — «Проверка»
  и «Выполнено ранее». Проверка: `backlog inspect-template templates/formular.md --json`
  называет values `requirement` и не называет `target`.
- [x] 1.2 Принять шаблон ядром. Проверка: `backlog check-template templates/formular.md` —
  код возврата `0`.

## 2. Навык-обёртка formular

- [x] 2.1 Написать `.claude/skills/formular/SKILL.md` по структуре навыка `workflow-fast`
  (решение 6 design.md): вход требования одним вопросом при пустом вызове, предмет
  `{YYYYMMDDHHMMSS}-{slug}`, вызов `/backlog:backlog-generate` с операцией `formular`
  и значением `requirement`, показ собранного вызова до прогона, передача исполнения
  `/backlog:backlog-run`, отказы как есть, версионирование 1.0.0 / WRSP-032. Проверка:
  фронтматтер несёт `name: formular`, порядок не предлагает `target`.
- [x] 2.2 Продублировать навык во вторую точку входа: `.zcode/skills/formular/SKILL.md`.
  Проверка: `diff .claude/skills/formular/SKILL.md .zcode/skills/formular/SKILL.md` — пуст.

## 3. Пробный прогон и сверка со спекой

- [x] 3.1 Породить пробный беклог: `backlog generate --operation formular` с предметом-пробой
  и коротким `requirement`. Проверка: `backlog lint <путь>` — код возврата `0`; после сверки
  пробный след удалён.
- [x] 3.2 Прогнать пробное требование с владельцем до стоп-знака: прожарка заполняет все
  девять полей карточки, статус `Draft` → `Proposed` при принятии; задача на GitHub
  не создаётся, ветка не открывается. Проверка: карточка `br_card` во фронтматтере несёт
  девять заполненных полей; `gh issue list` без новых задач; `git branch --show-current`
  прежний; сценарии `specs/formular-operation/spec.md` воспроизводятся; пробный след
  удалён либо оставлен по решению владельца.

## 4. Артефакт требования в docs/requirements (правка владельца 2026-11-21)

- [x] 4.1 Поднять шаблон `templates/formular.md` до версии 1.1.0: группа «4 Фиксация» —
  задача записи принятой карточки артефактом `docs/requirements/<ID>.md` по DOC-014
  и DOC-022; «Итог» становится группой 5 и называет путь артефакта. Проверка:
  `backlog check-template templates/formular.md` — код возврата `0`.
- [x] 4.2 Поднять оба `SKILL.md` до версии 1.0.1: продукт операции — артефакт
  `docs/requirements/<ID>.md`, `br_card` — рабочее значение прогона. Проверка: `diff`
  между `.claude` и `.zcode` копиями пуст.
- [x] 4.3 Зафиксировать принятую карточку первого прогона: `docs/requirements/BR-001.md`
  из `br_card` беклога `20261121234009-past-work-search`. Проверка: файл несёт девять полей
  и таблицу версий.
- [x] 4.4 Прогнать валидацию change. Проверка: `openspec validate add-formular-skill --strict` —
  код возврата `0`.

## 5. Линтинг карточки в операции (запрос владельца 2026-11-22)

- [x] 5.1 Положить линтер в репозиторий: `tools/reqlint/reqlint.py` (форк 0.2.0 с `--config`)
  и `tools/reqlint/rules.yml` (правила RU; починены E1 `\bPR\b` и D1 «прошлых»). Проверка:
  `python3 -I tools/reqlint/reqlint.py --config tools/reqlint/rules.yml --version` отвечает
  версией, конфиг грузится без ошибки.
- [x] 5.2 Поднять `templates/formular.md` до 1.2.0: задача 2.4 — линтер по значениям полей
  карточки; стоп-знак 3.1 называет находки `error` и решение владельца по каждой. Проверка:
  `backlog check-template templates/formular.md` — код возврата `0`.
- [x] 5.3 Прогнать шаг линтинга на карточке BR-001 (сверка поведения шага вне прогона):
  значения девяти полей — по строке на поле — через `tools/reqlint/`. Проверка: A3/B1/C1/D2
  находят слабые места полей; E1 не срабатывает на «Proposed»; D1 ловит «на трёх известных
  прошлых работах».
- [x] 5.4 Прогнать валидацию change. Проверка: `openspec validate add-formular-skill --strict` —
  код возврата `0`.

## Workflow follow-up

- Закоммитить по GIT-009 в ветку `feature/wrsp-032-requirement-formation-skill`: заголовок
  `WRSP-032: добавить навык формирования требования`, тело — перечень выполненной работы.
- После приёмки владельцем — `openspec archive add-formular-skill` (спека уйдёт
  в `openspec/specs/formular-operation/`) и закрытие issue #27.
