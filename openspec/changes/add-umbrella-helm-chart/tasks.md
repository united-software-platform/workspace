# Tasks

## 1. Чарт

- [x] 1.1 Создать чарт `deploy/workspace`: Chart.yaml, values.yaml (пустой `services` с примером в комментарии), templates/_helpers.tpl, templates/service.yaml (фабрика Deployment+Service ClusterIP), templates/NOTES.txt; YAML-файлы короткие и просмотрены; разбор и `helm lint deploy/workspace` переносятся на хост с helm — в среде ветки ни helm, ни PyYAML (пакет в закреплённый python не ставился)
- [x] 1.2 Добавить задачу mise `k3s-apply` (helm upgrade --install, неймспейс WORKSPACE_NAMESPACE с умолчанием workspace, --create-namespace); проверено — `mise tasks` её перечисляет

## 2. Связка и прогоны

- [x] 2.1 Указать чарт в ENV-007 `rules/environment.md` (ссылка на deploy/workspace и k3s-apply, норма кодом не пересказывается) и добавить строку в «Куда дальше» README.md
- [x] 2.2 Прогнать `openspec validate add-umbrella-helm-chart --strict` — valid; `git status` сверен с перечнем Impact из proposal.md

## Workflow follow-up

- `helm lint deploy/workspace`, разбор values и `mise run k3s-apply` на пустом наборе — на хосте
  владельца с helm и кластером k3s.
- Archive изменения после приёмки.
