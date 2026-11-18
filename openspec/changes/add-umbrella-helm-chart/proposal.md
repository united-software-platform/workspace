# Proposal

## Why

Стандарт окружения (change `unify-environment`) объявил helm единицей поставки сервисов дочерним
проектам (ENV-007), но носителя у стандарта нет. Первому потребителю общего набора сервис сам
workspace: ему нужны PostgreSQL, OpenSearch и S3 (MinIO) — заготовка поднимает их одним чартом,
а подключение будущего дочернего проекта делает механическим.

## What Changes

- Добавлен зонтичный helm-чарт `deploy/workspace`: общий набор — PostgreSQL 17.12,
  OpenSearch 3.9.0 (single-node), MinIO (закреплённый тег RELEASE) — по одному общему экземпляру
  в неймспейс применения; данные — PVC local-path (умолчание 10Gi на сервис).
- Сервисы поднимаются чистыми, без init-наполнения: БД, индексы и бакеты создают потребители
  (ENV-007 — разделение данных внутри общих сервисов).
- Секреты (пароли Postgres/OpenSearch, учётные данные MinIO) живут в `.env`, имена — в шаблоне
  `.env.example`; задача mise `k3s-apply` передаёт их в чарт ключами `--set`, пустой секрет
  останавливает установку сообщением.
- Доступ — `kubectl port-forward` (ENV-003): сервисы ClusterIP, порты на хост не публикуются.
- Каждый сервис — собственный шаблон; значения `app.kubernetes.io/component` используются
  в качестве селекторов.

## Capabilities

### New Capabilities

- `umbrella-chart`: зонтичный helm-чарт workspace — общий набор сервисов (PostgreSQL, OpenSearch,
  MinIO), поставляемый в неймспейс применения и разделяемый потребителями внутри сервисов.

### Modified Capabilities

(нет — изменение не трогает требования существующих спецификаций)

## Impact

Новые: `deploy/workspace/` (Chart.yaml, values.yaml, templates/_helpers.tpl,
templates/{postgres,opensearch,minio}.yaml, templates/NOTES.txt),
`openspec/changes/add-umbrella-helm-chart/`.

Правимые: `mise.toml` (задача k3s-apply с передачей кредов), `.env.example` (блок k3s-services),
`README.md` (предусловие `vm.max_map_count`), `rules/environment.md` (ссылка ENV-007 на чарт
и k3s-apply).
