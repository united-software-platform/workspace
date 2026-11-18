# Proposal

## Why

Стандарт окружения (change `unify-environment`) объявил helm единицей поставки сервисов дочерним
проектам (ENV-007), но носителя у стандарта нет: кластер после вырезки forge пуст, ни одного
чарта в репозитории нет. Заготовка делает стандарт применимым: включение сервиса общего набора —
правка values, а не написание манифестов с нуля.

## What Changes

- Добавлен зонтичный helm-чарт `deploy/workspace`: values-фабрика `services[]` ставит каждую
  позицию парой Deployment + Service (ClusterIP) в неймспейс применения; пустой набор ничего
  не ставит.
- Добавлена задача mise `k3s-apply`: применение чарта одной командой
  `helm upgrade --install` в неймспейс `WORKSPACE_NAMESPACE` (умолчание `workspace`).
- `rules/environment.md` (ENV-007) и `README.md` («Куда дальше») указывают на чарт и задачу.

## Capabilities

### New Capabilities

- `umbrella-chart`: зонтичный helm-чарт workspace — механизм, которым дочерние проекты получают
  сервисы общего набора в свой неймспейс.

### Modified Capabilities

(нет — изменение не трогает требования существующих спецификаций)

## Impact

Новые: `deploy/workspace/` (Chart.yaml, values.yaml, templates/_helpers.tpl,
templates/service.yaml, templates/NOTES.txt), `openspec/changes/add-umbrella-helm-chart/`.

Правимые: `mise.toml` (задача k3s-apply), `rules/environment.md` (ссылка на чарт в ENV-007),
`README.md` (строка «Куда дальше»).
