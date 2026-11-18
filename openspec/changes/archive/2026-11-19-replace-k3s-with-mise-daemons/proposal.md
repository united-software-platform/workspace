# Proposal

## Why

Стандарт окружения из change `unify-environment` ставит сервисы в локальный кластер k3s —
ради трёх stateful-сервисов это кластер с containerd, kubelet и API-server, доступ через
`kubectl port-forward`, отладка в два слоя. Владелец принял решение (2026-11-19): mise —
единственный менеджер окружения; сервисы поднимаются экспериментальной фичей mise daemons,
k3s, helm и docker compose из стандарта уходят. Экспериментальный статус фичи принят осознанно.

## What Changes

- **BREAKING** Сервисы общего набора (PostgreSQL, OpenSearch, MinIO) переводятся с helm-чарта
  в k3s на демоны mise в `mise.toml`: PostgreSQL — нативный пресет без контейнерного рантайма,
  OpenSearch и MinIO — image-демоны под docker/podman. Застейдженное удаление чарта
  `deploy/workspace` и change `add-umbrella-helm-chart` — часть этого перехода.
- **BREAKING** Доступ к сервисам: `kubectl port-forward` и предусловия `kubectl`/`helm`
  отменяются; демоны слушают фиксированные порты localhost, объявленные в `mise.toml`.
- Порты и координаты подключения стандартизованы: фиксированные порты в декларациях демонов,
  потребительская копия — переменные `PG_PORT`, `OPENSEARCH_PORT`, `MINIO_PORT` в секции
  `[env]` корневого `mise.toml` (каскад mise раздаёт их дочерним проектам).
- Переменные: паттерн ENV-005 сохраняется; секреты сервисов возвращаются в `.env`
  (`POSTGRES_PASSWORD`, `OPENSEARCH_ADMIN_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`),
  имена — в `.env.example`.
- Задачи mise: добавляются `env-up`, `env-down`, `env-status`; supervisor pitchfork закрепляется
  в `[tools]`.
- Одноразовые прогоны (tldr-сканирование): Job в k3s → одноразовый контейнер `docker run --rm`
  из задачи mise; `tools/tldr/scan.sh` возвращается к docker-механике с bind-mount.
- `rules/environment.md` переписывается: ENV-002..004, ENV-007 и ограничения описывают демоны,
  фиксированные порты и docker как предусловие вместо k3s.
- `README.md` переписывается: предусловие — docker/podman вместо кластера k3s, возвращается
  требование `vm.max_map_count=262144` (нужно OpenSearch и под docker), шаг подъёма сервисов —
  `mise run env-up`.
- Открытый change `unify-environment` приводится в соответствие: его дельта `specs/environment/`
  удаляется — capability `environment` создаётся этим изменением; дельта `specs/code-scan/`
  корректируется с Job-механики k3s на docker-механику.

## Capabilities

### New Capabilities

- `environment`: единый стандарт окружения зонтичного репозитория — mise как единственный
  менеджер: демоны общего набора сервисов, фиксированные локальные порты, паттерн переменных
  `[env]`/`.env`, задачи окружения, одноразовые прогоны контейнерами, зонтичная поставка
  демонами, принятие экспериментального статуса mise daemons.

### Modified Capabilities

(не изменяются: корректировка change `unify-environment` затрагивает его собственные
незакрытые артефакты, а не живые спеки)

## Impact

Правимые: `mise.toml`, `.env.example`, `.gitignore`, `rules/environment.md`, `README.md`,
`tools/tldr/scan.sh`, `tools/tldr/gateway.py` (докстринг), `tools/tldr/README.md`,
артефакты открытого change `unify-environment` (дельты `specs/environment/`, `specs/code-scan/`,
строка proposal о Job).

Новые: `openspec/changes/replace-k3s-with-mise-daemons/`.

Зависимости: docker или podman на хосте — предусловие для image-демонов и одноразовых
прогонов; mise с experimental-фичей daemons; pitchfork ставится через `[tools]`.
