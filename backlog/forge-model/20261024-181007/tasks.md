---
template_version: "1.2.1"
generated: "2026-10-24"
operation: forge-model
subject: "20261024-181007"
runner: "/backlog:backlog-run"
intent: "Перенести модель реестра проектов projects.yaml и её связи со словарём taxonomy.yaml в модель данных PostgreSQL (схема public). Декомпозиция модели на четыре смысловые части.

Часть 1 — метаданные моделей (блок meta обоих файлов). Таблица model_meta: model (имя модели, первичный ключ), version (текущая версия структуры, not null). Таблица model_history: model, version, date, source, summary; составной первичный ключ model+version; внешний ключ model на model_meta.model. Значения model — projects и taxonomy.

Часть 2 — словарь значений taxonomy.yaml, пять разделов отдельными таблицами: organization, project_group, technology, domain, role. Общие колонки раздела: id (строковый первичный ключ), name (text, not null), deprecated (boolean, not null), replaced_by_id (строка, nullable; внешний ключ на id той же таблицы). У organization дополнительно owned (boolean, not null). У technology дополнительно kind_id (строка, not null; внешний ключ на справочник technology_kind). Синонимы каждого раздела — отдельная таблица organization_synonym, project_group_synonym, technology_synonym, domain_synonym, role_synonym: составной первичный ключ (id раздела, synonym), внешний ключ на раздел.

Часть 3 — закрытые перечни фасетов. Справочник origin: id (первичный ключ), name (not null); значения commercial, personal, open-source, venture, experimental. Справочник project_status: id (первичный ключ), name (not null); значения active, finished, archived. Справочник technology_kind: id (первичный ключ), name (not null); значения language, framework, storage, infrastructure, practice.

Часть 4 — записи реестра projects.yaml. Таблица project: name (строка, первичный ключ, уникально), path (text, nullable, уникально среди непустых), purpose (text, not null), origin_id (not null, внешний ключ на origin.id), organization_id (not null, внешний ключ на organization.id), group_id (nullable, внешний ключ на project_group.id), customer_id (nullable, внешний ключ на organization.id — общий словарь организаций), period_from (integer, not null), period_to (integer, nullable), status_id (not null, внешний ключ на project_status.id). Многозначные фасеты — связующие таблицы project_technology (project_name, technology_id), project_domain (project_name, domain_id), project_role (project_name, role_id); у каждой составной первичный ключ и внешние ключи на project.name и соответствующий раздел словаря.

Связи модели: project ссылается на organization дважды (работодатель и заказчик), на project_group, origin и project_status; связующие таблицы ссылаются на project и на technology, domain, role; replaced_by_id каждой таблицы словаря ссылается на себя; model_history ссылается на model_meta. Ограничения, не выразимые форматом forge (согласованность status и period, запрет origin personal у организации с owned, формат сегмента пути, обязательность replaced_by при deprecated), в схеме не выражать — они остаются правилами приложения. Данные не переносить: операция строит только схему."
mode: auto
gate:
  close: >-
    Условие выполнено: forge status называет подтверждённую попытку 1
    (verdict success, confirmed_attempt 1). Закрываю операцию.
allow_drop: false
status: success
stop_reason: null
verdict:
  attempt_1: success
  attempt_2: null
  attempt_3: null
backlog:
  attempt_1: backlog/forge-apply/20261024-181007-1/tasks.md
  attempt_2: null
  attempt_3: null
trail:
  attempt_1: backlog/forge-model/20261024-181007/attempt-1
  attempt_2: backlog/forge-model/20261024-181007/attempt-2
  attempt_3: backlog/forge-model/20261024-181007/attempt-3
---

# Операция построения модели 20261024-181007

Беклог операции Liquibase Forge и её журнал: намерение, режим, три попытки с откатом, закрытие
и итоговый отчёт. След операции — `backlog/forge-model/20261024-181007/`, артефакты попытки N —
`backlog/forge-model/20261024-181007/attempt-N/`. Понятия — в `docs/domain.md`, команды CLI —
в `docs/architecture.md`.

Значения операции несёт фронтматтер — второй раз они не собираются
(BKL-005; текст нормы — `backlog norms --rule BKL-005`). Задачи исполняются по порядку;
группы попыток сформулированы как цели, а развилку по фронтматтеру решает CLI `forge`.

Порядок исполнения — отметки задач, выводимый признак «выполнено ранее», стоп-знак перед
закрытием — задан BKL-006 (`backlog norms --rule BKL-006`)
и BKL-007 (`backlog norms --rule BKL-007`), а его носитель —
`/backlog:backlog-run`: прочитать его перед первой задачей; здесь он
не пересказывается (BKL-008; текст нормы — `backlog norms --rule BKL-008`). Указатель носителя несёт
и фронтматтер значением `runner`. Тот же носитель исполняет каждый беклог попытки.

Отказ владельца, непройденный гейт и код `2` любой команды `forge` — здесь или в беклоге
попытки — прекращают и этот беклог: вызвать
`forge stop --operation backlog/forge-model/20261024-181007/tasks.md --reason <причина>`, где причина —
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

- [x] 1.1 Прочитать носитель порядка исполнения:
  `/backlog:backlog-run`
  - Проверка: порядок исполнения, стоп-знак и таблица исходов прочитаны до первой задачи
  - Выполнено ранее: файл прочитан в этом сеансе — повторное чтение без последствий
- [x] 1.2 Прогнать структурную проверку этого беклога: его путь назван передачей исполнения
  `backlog lint <путь этого беклога>`
  - Проверка: код возврата `0`, расхождений проверка не называет
  - Выполнено ранее: проверка состояния — повторяется без последствий
- [x] 1.3 Убедиться, что намерение записано, а тестовая среда доступна:
  `forge status --operation backlog/forge-model/20261024-181007/tasks.md`
  - Проверка: `intent` во фронтматтере непуст, код возврата `0`, статус операции `running`
  - Выполнено ранее: проверка состояния — повторяется без последствий

---

## 2. Попытка 1

- [x] 2.1 Породить беклог попытки 1:
  `backlog generate --operation forge-apply --subject 20261024-181007-1`
  `--value parent=backlog/forge-model/20261024-181007/tasks.md --value attempt=1`
  `--value trail=backlog/forge-model/20261024-181007/attempt-1 --flag first-attempt`
  `--flag auto`
  и `--flag allow-drop` при `allow_drop: true` во фронтматтере этого беклога, иначе
  `--no-flag allow-drop`; записать путь беклога попытки во фронтматтер в `backlog.attempt_1`
  - Проверка: беклог `backlog/forge-apply/20261024-181007-1/tasks.md` порождён, путь записан
  - Выполнено ранее: беклог попытки 1 лежит, `backlog.attempt_1` заполнено
- [x] 2.2 Загрузить `/backlog:backlog-run` и исполнить беклог `backlog/forge-apply/20261024-181007-1/tasks.md`;
  перенести его вердикт во фронтматтер в `verdict.attempt_1`
  - Проверка: `backlog verify` беклога попытки 1 — код `0`, `verdict.attempt_1` заполнено
  - Выполнено ранее: `verdict.attempt_1` заполнено и `backlog verify` беклога попытки — код `0`
- [x] 2.3 Не оставить в БД неподтверждённых изменений попытки 1:
  `forge rollback --operation backlog/forge-model/20261024-181007/tasks.md --attempt 1`
  - Проверка: код возврата `0`; при вердикте `failure` записан `attempt-1/rollback.json`
    с подтверждённым возвратом схемы
  - Выполнено ранее: вердикт `success` либо `attempt-1/rollback.json` подтверждает возврат

---

## 3. Попытка 2

- [x] 3.1 Породить беклог попытки 2, если модель ещё не подтверждена:
  `backlog generate --operation forge-apply --subject 20261024-181007-2`
  `--value parent=backlog/forge-model/20261024-181007/tasks.md --value attempt=2`
  `--value trail=backlog/forge-model/20261024-181007/attempt-2 --no-flag first-attempt`
  `--flag auto`
  и `--flag allow-drop` при `allow_drop: true` во фронтматтере этого беклога, иначе
  `--no-flag allow-drop`; записать путь беклога попытки во фронтматтер в `backlog.attempt_2`
  - Проверка: беклог попытки 2 порождён, путь записан
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 либо беклог попытки 2
    лежит и `backlog.attempt_2` заполнено
- [x] 3.2 Загрузить `/backlog:backlog-run` и исполнить беклог `backlog/forge-apply/20261024-181007-2/tasks.md`;
  перенести его вердикт во фронтматтер в `verdict.attempt_2`
  - Проверка: `backlog verify` беклога попытки 2 — код `0`, `verdict.attempt_2` заполнено
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 либо
    `verdict.attempt_2` заполнено
- [x] 3.3 Не оставить в БД неподтверждённых изменений попытки 2:
  `forge rollback --operation backlog/forge-model/20261024-181007/tasks.md --attempt 2`
  - Проверка: код возврата `0`; при вердикте `failure` записан `attempt-2/rollback.json`
    с подтверждённым возвратом схемы
  - Выполнено ранее: попытки 2 не было, вердикт `success` либо `attempt-2/rollback.json`
    подтверждает возврат

---

## 4. Попытка 3

- [x] 4.1 Породить беклог попытки 3, если модель ещё не подтверждена:
  `backlog generate --operation forge-apply --subject 20261024-181007-3`
  `--value parent=backlog/forge-model/20261024-181007/tasks.md --value attempt=3`
  `--value trail=backlog/forge-model/20261024-181007/attempt-3 --no-flag first-attempt`
  `--flag auto`
  и `--flag allow-drop` при `allow_drop: true` во фронтматтере этого беклога, иначе
  `--no-flag allow-drop`; записать путь беклога попытки во фронтматтер в `backlog.attempt_3`
  - Проверка: беклог попытки 3 порождён, путь записан
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 или 2 либо беклог
    попытки 3 лежит и `backlog.attempt_3` заполнено
- [x] 4.2 Загрузить `/backlog:backlog-run` и исполнить беклог `backlog/forge-apply/20261024-181007-3/tasks.md`;
  перенести его вердикт во фронтматтер в `verdict.attempt_3`
  - Проверка: `backlog verify` беклога попытки 3 — код `0`, `verdict.attempt_3` заполнено
  - Выполнено ранее: `forge status` называет подтверждённую попытку 1 или 2 либо
    `verdict.attempt_3` заполнено
- [x] 4.3 Не оставить в БД неподтверждённых изменений попытки 3 — после третьей неудачи это
  финальный откат: `forge rollback --operation backlog/forge-model/20261024-181007/tasks.md --attempt 3`
  - Проверка: код возврата `0`; при вердикте `failure` записан `attempt-3/rollback.json`
    с подтверждённым возвратом схемы
  - Выполнено ранее: попытки 3 не было, вердикт `success` либо `attempt-3/rollback.json`
    подтверждает возврат

---

## 5. Итог

- [x] 5.1 Автоматический гейт перед закрытием. Условие: `forge status` называет либо одну
  подтверждённую попытку, либо три попытки с вердиктом `failure` и подтверждённым откатом
  каждой. Записать решение и обоснование во фронтматтер в `gate.close` и закрыть операцию:
  `forge close --operation backlog/forge-model/20261024-181007/tasks.md`
  - Проверка: `gate.close` заполнено, `status` — `success` либо `failure`; при `success`
    модель и changelog приняты в `db/`
  - Выполнено ранее: `status` во фронтматтере — `success` либо `failure`
- [x] 5.2 Вернуть LLM итоговый отчёт:
  `forge report --operation backlog/forge-model/20261024-181007/tasks.md`
  - Проверка: отчёт содержит статус, число попыток, пути к модели и changelog, результаты
    сверки и перечень беклогов
  - Выполнено ранее: отчёт возвращён в этом сеансе

---

## Версионирование

| Версия | Дата | Задача | Агент | Модель | Описание изменений |
|--------|------|--------|-------|--------|--------------------|
| 1.0.0 | 2026-10-24 | Операция построения модели 20261024-181007 | backlog | — | Беклог порождён по шаблону версии 1.2.1 |

Отметки об исполнении задач записями в таблицу не сопровождаются: беклог исполняется,
а не правится.
