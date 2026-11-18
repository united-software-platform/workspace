# Spec Delta

## Purpose

Зонтичный helm-чарт workspace: общий набор сервисов — PostgreSQL, OpenSearch, MinIO — поставляется в неймспейс применения и разделяется потребителями внутри сервисов, без публикации портов.

## ADDED Requirements

### Requirement: Общий набор из трёх сервисов

Чарт `deploy/workspace` SHALL ставить в неймспейс применения по одному общему экземпляру
PostgreSQL, OpenSearch и MinIO. Версии образов MUST быть закреплены полными тегами и задаваться
в values; секреты в values не задаются.

#### Scenario: Применение поднимает набор

- **WHEN** чарт применяется с заполненными кредами
- **THEN** в неймспейсе применения поднимаются по одному Deployment и Service каждого сервиса

#### Scenario: Версии закреплены

- **WHEN** значения образов сверяются с values
- **THEN** все три тега — полные версии, ни один не `latest`

### Requirement: Креды передаются при применении

Задача `mise run k3s-apply` SHALL передавать секреты в чарт ключами `--set` из переменных
окружения `POSTGRES_PASSWORD`, `OPENSEARCH_ADMIN_PASSWORD`, `MINIO_ROOT_USER`,
`MINIO_ROOT_PASSWORD`. Секретные значения MUST храниться только в git-ignored `.env`;
пустое значение MUST останавливать установку с сообщением об отсутствующем секрете.

#### Scenario: Секрет не задан

- **WHEN** `k3s-apply` выполняется с пустым `POSTGRES_PASSWORD`
- **THEN** helm отказывает с сообщением про отсутствующий `postgres.password`, объекты не ставятся

#### Scenario: Секрет не в git

- **WHEN** пользователь заполняет `.env` реальными значениями
- **THEN** `git status` не показывает `.env`, а `.env.example` содержит только имена

### Requirement: Чистое начальное состояние

Установка MUST NOT наполнять сервисы: PostgreSQL поднимается без пользовательских БД, OpenSearch —
без индексов, MinIO — без бакетов; инициализирующих Job'ов установка не запускает. Наполнение —
дело потребителей, разделяющих общие экземпляры по ENV-007.

#### Scenario: После установки

- **WHEN** установка завершилась успешно
- **THEN** у postgres нет пользовательских БД сверх системных, в opensearch нет индексов,
  в minio нет бакетов

### Requirement: Хранение в PVC

Данные каждого сервиса SHALL жить в PersistentVolumeClaim (класс local-path k3s по умолчанию)
с размером из values; умолчание — 10Gi на сервис.

#### Scenario: Перезапуск сохраняет данные

- **WHEN** под сервиса пересоздаётся после записи данных
- **THEN** данные доступны новому поду из того же PVC

### Requirement: Доступ без публикации портов

Сервисы чарта MUST быть ClusterIP без NodePort и иного маппинга на хост; доступ —
`kubectl port-forward` на время обращения.

#### Scenario: Подключение к postgres

- **WHEN** потребителю нужно подключиться к postgres с хоста
- **THEN** он выполняет `kubectl port-forward svc/workspace-postgres 5432:5432`; постоянной
  публикации порта не возникает

### Requirement: Применение одной задачей mise

Задача `mise run k3s-apply` SHALL применять чарт командой `helm upgrade --install workspace
deploy/workspace` в неймспейс из переменной `WORKSPACE_NAMESPACE` (умолчание — `workspace`),
создавая неймспейс при отсутствии. Повторное применение с теми же values и секретами MUST быть
идемпотентным.

#### Scenario: Повторное применение

- **WHEN** `mise run k3s-apply` выполняется второй раз без изменения values и `.env`
- **THEN** helm не меняет число объектов и подов в кластере
