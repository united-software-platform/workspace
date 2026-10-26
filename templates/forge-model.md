<!-- template_version: 1.2.1 -->
---
template_version: "{{template_version}}"
generated: "{{date}}"
operation: {{operation}}
subject: "{{subject}}"
runner: "{{runner}}"
intent: {{intent_scalar}}
{{#auto}}
mode: auto
gate:
  close: null
{{/auto}}
{{^auto}}
mode: interactive
confirmed:
  close: null
{{/^auto}}
{{#allow-drop}}
allow_drop: true
{{/allow-drop}}
{{^allow-drop}}
allow_drop: false
{{/^allow-drop}}
status: running
stop_reason: null
verdict:
  attempt_1: null
  attempt_2: null
  attempt_3: null
backlog:
  attempt_1: null
  attempt_2: null
  attempt_3: null
trail:
  attempt_1: backlog/forge-model/{{subject}}/attempt-1
  attempt_2: backlog/forge-model/{{subject}}/attempt-2
  attempt_3: backlog/forge-model/{{subject}}/attempt-3
---

# Операция построения модели {{subject}}

Беклог операции Liquibase Forge и её журнал: намерение, режим, три попытки с откатом, закрытие
и итоговый отчёт. След операции — `backlog/forge-model/{{subject}}/`, артефакты попытки N —
`backlog/forge-model/{{subject}}/attempt-N/`. Понятия — в `docs/domain.md`, команды CLI —
в `docs/architecture.md`.

Значения операции несёт фронтматтер — второй раз они не собираются
(BKL-005; текст нормы — `backlog norms --rule BKL-005`). Задачи исполняются по порядку;
группы попыток сформулированы как цели, а развилку по фронтматтеру решает CLI `forge`.

Порядок исполнения — отметки задач, выводимый признак «выполнено ранее», стоп-знак перед
закрытием — задан BKL-006 (`backlog norms --rule BKL-006`)
и BKL-007 (`backlog norms --rule BKL-007`), а его носитель —
`{{runner}}`: прочитать его перед первой задачей; здесь он
не пересказывается (BKL-008; текст нормы — `backlog norms --rule BKL-008`). Указатель носителя несёт
и фронтматтер значением `runner`. Тот же носитель исполняет каждый беклог попытки.

Отказ владельца, непройденный гейт и код `2` любой команды `forge` — здесь или в беклоге
попытки — прекращают и этот беклог: вызвать
`forge stop --operation backlog/forge-model/{{subject}}/tasks.md --reason <причина>`, где причина —
отказ, решение гейта либо диагностика команды, и остановиться. Статус операции правит только
CLI `forge`. Попытка при этом не расходуется, повторный вызов навыка `forge` продолжает
с задачи, признак которой не выполнен. Владелец, который передумал, бросает операцию вызовом
навыка `/forge --abandon "<причина>"`: начатые попытки откатываются, операция закрывается
статусом `abandoned`; сам беклог операцию не бросает.

---

## Навигация

- [Предусловия](#1-предусловия)
- [Попытка 1](#2-попытка-1)
- [Попытка 2](#3-попытка-2)
- [Попытка 3](#4-попытка-3)
- [Итог](#5-итог)
- [Версионирование](#версионирование)

---

## 1. Предусловия

- [ ] 1.1 Прочитать носитель порядка исполнения:
  `{{runner}}`
  - Проверка: порядок исполнения, стоп-знак и таблица исходов прочитаны до первой задачи
  - Выполнено ранее: файл прочитан в этом сеансе — повторное чтение без последствий
- [ ] 1.2 Прогнать структурную проверку этого беклога: его путь назван передачей исполнения
  `backlog lint <путь этого беклога>`
  - Проверка: код возврата `0`, расхождений проверка не называет
  - Выполнено ранее: проверка состояния — повторяется без последствий
- [ ] 1.3 Убедиться, что намерение записано, а тестовая среда доступна:
  `forge status --operation backlog/forge-model/{{subject}}/tasks.md`
  - Проверка: `intent` во фронтматтере непуст, код возврата `0`, статус операции `running`
  - Выполнено ранее: проверка состояния — повторяется без последствий

---

## 2. Попытка 1

- [ ] 2.1 Породить беклог попытки 1:
  `backlog generate --operation forge-apply --subject {{subject}}-1`
  `--value parent=backlog/forge-model/{{subject}}/tasks.md --value attempt=1`
  `--value trail=backlog/forge-model/{{subject}}/attempt-1 --flag first-attempt`
{{#auto}}
  `--flag auto`
{{/auto}}
{{^auto}}
  `--no-flag auto`
{{/^auto}}
  и `--flag allow-drop` при `allow_drop: true` во фронтматтере этого беклога, иначе
  `--no-flag allow-drop`; записать путь беклога попытки во фронтматтер в `backlog.attempt_1`
  - Проверка: беклог `backlog/forge-apply/{{subject}}-1/tasks.md` порождён, путь записан
  - Выполнено ранее: беклог попытки 1 лежит, `backlog.attempt_1` заполнено
- [ ] 2.2 Загрузить `{{runner}}` и исполнить беклог `backlog/forge-apply/{{subject}}-1/tasks.md`;
  перенести его вердикт во фронтматтер в `verdict.attempt_1`
  - Проверка: `backlog verify` беклога попытки 1 — код `0`, `verdict.attempt_1` заполнено
  - Выполнено ранее: `verdict.attempt_1` заполнено и `backlog verify` беклога попытки — код `0`
- [ ] 2.3 Не оставить в БД неподтверждённых изменений попытки 1:
  `forge rollback --operation backlog/forge-model/{{subject}}/tasks.md --attempt 1`
  - Проверка: код возврата `0`; при вердикте `failure` записан `attempt-1/rollback.json`
    с подтверждённым возвратом схемы
  - Выполнено ранее: вердикт `success` либо `attempt-1/rollback.json` подтверждает возврат

---

## 3. Попытка 2

- [ ] 3.1 Породить беклог попытки 2, если модель ещё не подтверждена:
  `backlog generate --operation forge-apply --subject {{subject}}-2`
  `--value parent=backlog/forge-model/{{subject}}/tasks.md --value attempt=2`
  `--value trail=backlog/forge-model/{{subject}}/attempt-2 --no-flag first-attempt`
{{#auto}}
  `--flag auto`
{{/auto}}
{{^auto}}
  `--no-flag auto`
{{/^auto}}
  и `--flag allow-drop` при `allow_drop: true` во фронтматтере этого беклога, иначе
  `--no-flag allow-drop`; записать путь беклога попытки во фронтматтер в `backlog.attempt_2`
  - Проверка: беклог попытки 2 порождён, путь записан
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 либо беклог попытки 2
    лежит и `backlog.attempt_2` заполнено
- [ ] 3.2 Загрузить `{{runner}}` и исполнить беклог `backlog/forge-apply/{{subject}}-2/tasks.md`;
  перенести его вердикт во фронтматтер в `verdict.attempt_2`
  - Проверка: `backlog verify` беклога попытки 2 — код `0`, `verdict.attempt_2` заполнено
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 либо
    `verdict.attempt_2` заполнено
- [ ] 3.3 Не оставить в БД неподтверждённых изменений попытки 2:
  `forge rollback --operation backlog/forge-model/{{subject}}/tasks.md --attempt 2`
  - Проверка: код возврата `0`; при вердикте `failure` записан `attempt-2/rollback.json`
    с подтверждённым возвратом схемы
  - Выполнено ранее: попытки 2 не было, вердикт `success` либо `attempt-2/rollback.json`
    подтверждает возврат

---

## 4. Попытка 3

- [ ] 4.1 Породить беклог попытки 3, если модель ещё не подтверждена:
  `backlog generate --operation forge-apply --subject {{subject}}-3`
  `--value parent=backlog/forge-model/{{subject}}/tasks.md --value attempt=3`
  `--value trail=backlog/forge-model/{{subject}}/attempt-3 --no-flag first-attempt`
{{#auto}}
  `--flag auto`
{{/auto}}
{{^auto}}
  `--no-flag auto`
{{/^auto}}
  и `--flag allow-drop` при `allow_drop: true` во фронтматтере этого беклога, иначе
  `--no-flag allow-drop`; записать путь беклога попытки во фронтматтер в `backlog.attempt_3`
  - Проверка: беклог попытки 3 порождён, путь записан
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 или 2 либо беклог
    попытки 3 лежит и `backlog.attempt_3` заполнено
- [ ] 4.2 Загрузить `{{runner}}` и исполнить беклог `backlog/forge-apply/{{subject}}-3/tasks.md`;
  перенести его вердикт во фронтматтер в `verdict.attempt_3`
  - Проверка: `backlog verify` беклога попытки 3 — код `0`, `verdict.attempt_3` заполнено
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 или 2 либо
    `verdict.attempt_3` заполнено
- [ ] 4.3 Не оставить в БД неподтверждённых изменений попытки 3 — после третьей неудачи это
  финальный откат: `forge rollback --operation backlog/forge-model/{{subject}}/tasks.md --attempt 3`
  - Проверка: код возврата `0`; при вердикте `failure` записан `attempt-3/rollback.json`
    с подтверждённым возвратом схемы
  - Выполнено ранее: попытки 3 не было, вердикт `success` либо `attempt-3/rollback.json`
    подтверждает возврат

---

## 5. Итог

{{#auto}}
- [ ] 5.1 Автоматический гейт перед закрытием. Условие: `forge status` называет либо одну
  подтверждённую попытку, либо три попытки с вердиктом `failure` и подтверждённым откатом
  каждой. Записать решение и обоснование во фронтматтер в `gate.close` и закрыть операцию:
  `forge close --operation backlog/forge-model/{{subject}}/tasks.md`
  - Проверка: `gate.close` заполнено, `status` — `success` либо `failure`; при `success`
    модель и changelog приняты в `db/`
  - Выполнено ранее: `status` во фронтматтере — `success` либо `failure`
{{/auto}}
{{^auto}}
- [ ] 5.1 **Стоп-знак.** Показать владельцу исход из `forge status`: при подтверждённой попытке —
  её модель и changelog и то, что они станут принятым состоянием в `db/`; после трёх неудач —
  расхождения каждой попытки и то, что в `db/` ничего не изменится. Дождаться подтверждения,
  записать его во фронтматтер в `confirmed.close` и закрыть операцию:
  `forge close --operation backlog/forge-model/{{subject}}/tasks.md`
  - Проверка: подтверждение записано, `status` — `success` либо `failure`; при `success`
    модель и changelog приняты в `db/`
  - Выполнено ранее: `status` во фронтматтере — `success` либо `failure`
{{/^auto}}
- [ ] 5.2 Вернуть LLM итоговый отчёт:
  `forge report --operation backlog/forge-model/{{subject}}/tasks.md`
  - Проверка: отчёт содержит статус, число попыток, пути к модели и changelog, результаты
    сверки и перечень беклогов
  - Выполнено ранее: отчёт возвращён в этом сеансе

---

## Версионирование

| Версия | Дата | Задача | Агент | Модель | Описание изменений |
|--------|------|--------|-------|--------|--------------------|
| 1.0.0 | {{date}} | Операция построения модели {{subject}} | backlog | — | Беклог порождён по шаблону версии {{template_version}} |

Отметки об исполнении задач записями в таблицу не сопровождаются: беклог исполняется,
а не правится.
