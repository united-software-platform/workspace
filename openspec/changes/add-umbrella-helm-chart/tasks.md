# Tasks

## 1. Чарт

- [x] 1.1 Переписать values.yaml: секции postgres/opensearch/minio с закреплёнными образами (17.12, 3.9.0, RELEASE-тег), storage 10Gi, несекретные умолчания; секретов в values нет
- [x] 1.2 Заменить фабрику templates/service.yaml на три шаблона: postgres.yaml (PGDATA, pg_isready), opensearch.yaml (single-node, heap 512m, начальный пароль), minio.yaml (server + console, root-креды) — каждый PVC + Deployment + Service ClusterIP, селектор app.kubernetes.io/component, креды через required
- [x] 1.3 Переписать templates/NOTES.txt: состав набора, port-forward для всех троих, разделение потребителей, идемпотентность

## 2. Применение и связки

- [x] 2.1 Задача mise k3s-apply передаёт креды --set-ключами из POSTGRES_PASSWORD, OPENSEARCH_ADMIN_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD; проверено — `mise tasks` перечисляет задачу с обновлённым описанием
- [x] 2.2 Добавить блок k3s-services в .env.example с именами кред
- [x] 2.3 README: предусловие vm.max_map_count=262144 для OpenSearch; строка k3s-apply в «Куда дальше» уже стоит

## 3. Артефакты и прогоны

- [x] 3.1 Переписать proposal и spec-дельту umbrella-chart под прожаренный дизайн (каркас с шаблонами на сервис, состав набора, креды, PVC, port-forward, чистое состояние); прогнать `openspec validate add-umbrella-helm-chart --strict`
- [x] 3.2 Сверить `git status` с перечнем Impact из proposal.md

## Workflow follow-up

- `helm lint deploy/workspace` и `mise run k3s-apply` с заполненным `.env` — на хосте владельца
  с helm и кластером k3s; затем port-forward-проверки postgres/opensearch/minio.
- Archive изменения после приёмки.
