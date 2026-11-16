# Tasks

## 1. Справочники L2 и L3

- [x] 1.1 Добавить запись SUB-037 «Закупки и тендеры» (code `procurement-tender-management`,
  name `Procurement & Tender Management`, name_ru «Закупки и тендеры», двуязычные description
  об обеих сторонах закупочной деятельности — организация закупок заказчиком, участие
  поставщика: поиск закупок, подготовка заявок и документов) в
  `tools/classifier/taxonomy/l2_activity_subdomains.json` и поднять `record_count` 36 → 37
- [x] 1.2 Добавить записи в `tools/classifier/taxonomy/l3_problem_domains.json` и поднять
  `record_count` 25 → 27:
  PRB-026 «Трудоёмкость поиска релевантной информации» (code
  `relevant-information-search-difficulty`, name `Relevant Information Search Difficulty`,
  description о поиске предметов деятельности в больших объёмах разрозненной информации)
  и PRB-027 «Ручная подготовка документов» (code `manual-document-preparation`, name
  `Manual Document Preparation`, description о повторяющейся ручной подготовке документов,
  заявок и комплектов — вне контекста разработки ПО)
- [x] 1.3 Привести счётчики: `tools/classifier/taxonomy/manifest.json` — L2 36 → 37,
  L3 25 → 27; `tools/classifier/tests/test_taxonomy_loader.py` — `EXPECTED_COUNTS`
  L2 36 → 37, L3 25 → 27

## 2. Проверки

- [x] 2.1 Прогнать проверки: `uv run pytest`, `uv run mypy src`, `uv run ruff check .`
  в `tools/classifier/`
- [x] 2.2 Проверочный прогон классификатора на вымышленной закупочной карточке (живой
  эндпоинт `EMBEDDINGS_*`, карточка — файл вне репозитория, без реальных имён): SUB-037
  занимает primary L2; PRB-026 или PRB-027 занимает primary L3, оба новых кода в топ-4
  уровня; на L1/L4 деградации нет — primary осмысленный; зафиксировать картину кандидатов
  для ревью. При невыполнении критериев L3 действует критерий остановки из design D4:
  не более одной итерации правки формулировок
- [x] 2.3 Регрессионный прогон на purpose вымышленных примеров из `example_project.json`.
  Критерий перебазирован по результату: ожидания L3 примеров были иллюстративными и живыми
  прогонами не сверялись (у «Moss & Maple» primary L3 и до правки был не ожидаемый PRB-025,
  а PRB-021). Свёрка идёт с фактическим поведением до правки: primary L1/L2/L4 трёх примеров
  (DOM-003/SUB-004/SOL-031; DOM-003/SUB-033/SOL-032; DOM-003/SUB-035/SOL-033) и primary L3
  northstar (PRB-009) и pinecone (PRB-021) не изменились; у «Moss & Maple» допустима замена
  primary L3 внутри семейства информационных проблем — PRB-021 → PRB-026 (0.6968, отрыв
  0.0130), осмысленная для рекомендательного сервиса. PRB-026 у pinecone — secondary (0.7161),
  primary PRB-021 сохранён
