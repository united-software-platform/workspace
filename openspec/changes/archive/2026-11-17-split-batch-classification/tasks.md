# Tasks

## 1. Переименование навыка enrich-прогона

- [x] 1.1 Переименовать каталог навыка `git mv .claude/skills/classify-batch .claude/skills/classify-batch-enrich`, поправить заголовок и назначение `SKILL.md` на имя `classify-batch-enrich`, дозаписать строку версий (частичное изменение 1.0.1, задача — issue GitHub). Проверка: каталога `.claude/skills/classify-batch` нет, `git status` показывает rename, заголовок и назначение названы новым именем.
- [x] 1.2 Проверить ссылки на старое имя: поиск `grep -rn "classify-batch" --include="*.md"` вне архива OpenSpec и каталогов прогонов называет только новый карточный навык и обновлённые документы. Проверка: брошенных ссылок на enrich-прогон под старым именем нет.

## 2. Шаблон операции classify-card-auto

- [x] 2.1 Создать `templates/classify-card-auto.md` по каркасу `classify-project-auto.md`: без групп поиска и выбора источника, без цикла дополнения, один вызов утилиты; значения операции `card_json`, `threshold`, `package_stamp`, `item_number`, `runner_model`; фронтматтер без полей поиска и дополнения. Проверка: `backlog check-template templates/classify-card-auto.md` — код возврата `0`.
- [x] 2.2 Породить пробный беклог `backlog generate --operation classify-card-auto --subject test-card-auto --value card_json='{"name":"test","purpose":"тест"}' --value threshold=0.5 --value package_stamp=test --value item_number=01 --value runner_model=haiku` и прогнать `backlog lint` и `backlog verify` на порождённом беклоге. Проверка: обе проверки дают код `0`; пробный беклог удаляется после прогона.

## 3. Навык classify-batch (карточный прогон)

- [x] 3.1 Создать `.claude/skills/classify-batch/SKILL.md`: вход — JSON-массив карточек текстом вызова либо путь к файлу вне репозитория, нормализация массива до запуска агентов (брак — стоп с перечнем индексов), умолчания модели `haiku` и порога `0.5`, окружение `EMBEDDINGS_*` и таксономия без `WEBSEARCH_*`, штамп, разложенные заранее карточки `projects/{штамп}.cards/item-NN.json`, фоновые агенты по одному на карточку с операцией `classify-card-auto`, один итоговый файл `projects/{штамп}.json` с `source: null`, сводный отчёт. Проверка: навык описан по [DOC-014](../../../rules/documentation-rules.md#структура-файла), таблица версий ведётся по [DOC-022](../../../rules/documentation-rules.md#жизненный-цикл-документа).

## 4. Проверка целостности

- [x] 4.1 Прогнать контрольные проверки: `openspec validate split-batch-classification --strict` — без ошибок; `grep -rn "classify-batch" .claude templates --include="*.md"` показывает ровно два навыка без пересечений имён. Проверка: обе команды дают чистый результат.
- [x] 4.2 Сверить состав изменений с proposal: `git status --porcelain` показывает только переименованный навык, новый навык, новый шаблон и артефакты изменения; все новые и изменённые md-файлы следуют [DOC-014](../../../rules/documentation-rules.md#структура-файла) и ведут таблицу версий по [DOC-022](../../../rules/documentation-rules.md#жизненный-цикл-документа). Проверка: состав соответствует proposal.
