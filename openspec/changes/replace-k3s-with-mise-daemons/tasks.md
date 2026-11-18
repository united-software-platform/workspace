# Tasks

## 1. Декларации демонов и переменные

- [x] 1.1 Заполнить `mise.toml`: `[settings] experimental = true`; в `[tools]` добавить
  `pitchfork`; объявить `[daemons.postgres]` (нативный пресет, закреплённый последний
  мажор 18, порт 5432), `[daemons.opensearch]` (демон docker-запуска
  `opensearchproject/opensearch:3.10.0`, порт 9200, `discovery.type=single-node`) и
  `[daemons.minio]` (демон docker-запуска `ghcr.io/united-software-platform/minio` —
  собственной сборки форка — с закреплённым тегом RELEASE, порт 9000); проверить
  синтаксис `mise daemons ls` без запуска
- [x] 1.2 Добавить в `[env]` корневого `mise.toml` координаты подключения `PG_PORT=5432`,
  `OPENSEARCH_PORT=9200`, `MINIO_PORT=9000`; проверить `mise env` показывает переменные
- [x] 1.3 Вернуть в `.env.example` блок секретов сервисов с помеченными границами:
  `POSTGRES_PASSWORD`, `OPENSEARCH_ADMIN_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
  (имена с пустыми значениями, комментарий про общий набор); проверить `git status -- .env.example`
- [x] 1.4 Вынести данные демонов из рабочего дерева git: каталог данных (например `.data/`)
  в декларациях `data_dir` и запись в `.gitignore`; проверить `git status` не видит каталог
  после локального запуска
- [x] 1.5 Проверить на хосте с docker: передачу секретов и аргументов команды image-демонам;
  при недостаточности — перевести opensearch/minio в `run`-форму `docker run` с шаблонами
  `{{ env.* }}` (контракт задач не меняется); зафиксировать работающую форму в `mise.toml`

## 2. Задачи окружения

- [x] 2.1 Добавить задачи `env-up` (запуск демонов с ожиданием готовности), `env-down`
  (остановка), `env-status` (состояние демонов + сверка портов деклараций с `[env]`);
  проверить `mise tasks` перечисляет их с описаниями
- [x] 2.2 Проверить на хосте с docker полный цикл: `mise run env-up` → `env-status`
  показывает готовность тройки → psql/curl/mc по localhost-портам → `env-down` без остатка
  (`docker ps` пуст по нашим образам)

## 3. Одноразовые прогоны

- [x] 3.1 Перевести `tools/tldr/scan.sh` с Job/kubectl на `docker run --rm`: bind-mount
  проекта readOnly, bind-mount каталога отчётов rw, коды возврата 0/1/2 сохранены, код 2 —
  «нет docker»; проверить `sh -n` и запуск без аргументов (код 2)
- [x] 3.2 Сверить `tools/tldr/gateway.py` с новой механикой scan.sh (контракт и коды не
  менялись, докстринг без k3s/kubectl); проверить `python3 -m py_compile`
- [x] 3.3 Обновить `tools/tldr/README.md` под docker-механику запуска; проверить упоминаний
  k3s/kubectl не осталось: `grep -ri 'k3s\|kubectl\|helm' tools/tldr/` пусто

## 4. Правила и документы входа

- [x] 4.1 Переписать `rules/environment.md`: назначение и ENV-002 (демоны mise вместо k3s,
  compose по-прежнему запрещён), ENV-003 (фиксированные localhost-порты вместо port-forward),
  ENV-004 (состояние декларируется декларациями демонов), ENV-007 (поставка демонами через
  каскад, выделенный экземпляр — собственная декларация), дополнить ENV-001 словом о pitchfork;
  ограничения: docker/podman как предусловие, экспериментальный статус; запись таблицы версий
  1.1.0; проверить ссылочную целостность кодов ENV из других документов
- [x] 4.2 Переписать `README.md`: «Что нужно» — mise и docker/podman, `vm.max_map_count=262144`
  (OpenSearch и под docker), шаг подъёма сервисов `mise run env-up`; «Куда дальше» — env-down,
  env-status; «Ограничения» — docker-предусловие, экспериментальный статус daemons вместо
  Linux-ограничения k3s; проверить `grep -ri 'k3s\|kubectl\|helm' README.md` пусто
- [x] 4.3 Проверить перечни `CLAUDE.md` и `AGENTS.md`: правила окружения подключены, состав
  не менялся (ссылки на `rules/environment.md` действительны)

## 5. Согласование открытого change unify-environment

- [x] 5.1 Удалить из change `unify-environment` дельту `specs/environment/spec.md` целиком
  и строку New Capability `environment` в его proposal (capability создаётся этим изменением);
  в его proposal/design добавить запись о переносе стандарта окружения сюда; проверить
  `openspec validate unify-environment --strict` — valid
- [x] 5.2 Скорректировать дельту `specs/code-scan/spec.md` change `unify-environment`
  с Job-механики k3s на docker-механику: редакция кодов возврата — код 2 «нет docker» вместо
  «нет kubectl», сценарий «Нет kubectl» → «Нет docker», упоминания Job в текстах задач mise —
  на одноразовый контейнер; проверить `openspec validate unify-environment --strict`

## 6. Проверки изменения

- [x] 6.1 Прогнать проверки по затронутым файлам: `openspec validate replace-k3s-with-mise-daemons
  --strict` (valid), `sh -n tools/tldr/scan.sh`, `python3 -m py_compile tools/tldr/gateway.py`,
  `mise tasks` разбирает задачи; итоговый `git status` сверен с перечнем Impact из proposal.md

## Workflow follow-up

- Полный прогон `mise run tldr-scan` (образ tldr ~1 ГБ, загрузка при первом запуске).
- Archive в порядке: `unify-environment`, затем это изменение; после — коммит и PR по
  запросу владельца (код задачи по GIT-010 уточнить у владельца).
- Образ minio живёт в форке `united-software-platform/minio`: workflow `build-image.yml`
  еженедельно пересобирает свежайший upstream-тег в ghcr (без логинов для потребителей);
  обновление закреплённого тега в `mise.toml` — отдельным изменением.
