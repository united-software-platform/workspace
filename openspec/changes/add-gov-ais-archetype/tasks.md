# Tasks

## 1. Справочник L4

- [x] 1.1 Добавить запись SOL-035 «Государственная автоматизированная информационная система»
  (code `government-information-system`, name `Government Information System`, англ.
  description в стиле действующих) в `tools/classifier/taxonomy/l4_solution_archetypes.json`
  и поднять `record_count` 34 → 35
- [x] 1.2 Привести счётчики манифеста: `tools/classifier/taxonomy/manifest.json` — L4
  34 → 35, `example_project.json` 3 → 4

## 2. Вымышленный пример

- [x] 2.1 Добавить в `tools/classifier/taxonomy/example_project.json` вымышленный пример
  «Region Support Registry — государственная АИС отчётности и реестров» (`fictional: true`,
  purpose профиля государственной АИС) с ожидаемым назначением DOM-002 / SUB-005 / PRB-003 /
  SOL-035 primary и поднять `record_count` 3 → 4

## 3. Тест и проверки

- [x] 3.1 Поднять `EXPECTED_COUNTS` для L4 до 35 в
  `tools/classifier/tests/test_taxonomy_loader.py`
- [x] 3.2 Прогнать проверки: `uv run pytest`, `uv run mypy src`, `uv run ruff check .`
  в `tools/classifier/`
- [x] 3.3 Проверочный прогон классификатора на карточке по purpose вымышленного примера
  (живой эндпоинт `EMBEDDINGS_*`): SOL-035 — primary L4 с confidence ≥ 0.5,
  `needs_confirmation: false`; SOL-001 теряет primary, допустим в secondary
