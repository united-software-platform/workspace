# Spec Delta

## REMOVED Requirements

### Requirement: Шаблон операции formular

**Reason**: операция `formular` переименована в `requirement-add` вместе со шаблоном —
имя файла шаблона является ключом операции беклог-плагина.
**Migration**: требование «Шаблон операции requirement-add» capability
`requirement-add-operation` — `templates/requirement-add.md`,
`backlog generate --operation requirement-add`.

### Requirement: Значения операции formular

**Reason**: операция переименована в `requirement-add`.
**Migration**: требование «Значения операции requirement-add» capability
`requirement-add-operation`; значение `requirement` и ключи фронтматтера не изменились.

### Requirement: Прожарка BR по шаблону карточки

**Reason**: операция переименована в `requirement-add`.
**Migration**: одноимённое требование capability `requirement-add-operation`; состав девяти
полей карточки и порядок прожарки не изменились.

### Requirement: Линтинг карточки перед стоп-знаком

**Reason**: операция переименована в `requirement-add`.
**Migration**: одноимённое требование capability `requirement-add-operation`; вызов линтера
`tools/reqlint/reqlint.py` с `tools/reqlint/rules.yml` не изменился.

### Requirement: Статусы карточки на стоп-знаке

**Reason**: операция переименована в `requirement-add`.
**Migration**: одноимённое требование capability `requirement-add-operation`; жизненный цикл
`Draft` / `Proposed` / `Rejected` не изменился.

### Requirement: Артефакт требования в docs/requirements

**Reason**: capability переименована в `requirement-add-operation` вместе с операцией.
**Migration**: одноимённое требование capability `requirement-add-operation`; формат артефакта
`docs/requirements/<ID>.md` не изменился.

### Requirement: Границы операции

**Reason**: операция переименована в `requirement-add`.
**Migration**: одноимённое требование capability `requirement-add-operation`; запрет работы
с GitHub не изменился.

### Requirement: Вход навыка formular

**Reason**: навык переименован в `requirement-add` — имя точки входа отвечает на вопрос
«что сделает владелец», а не называет внутреннюю операцию.
**Migration**: требование «Вход навыка requirement-add» capability `requirement-add-operation`;
навык лежит в `.claude/skills/requirement-add/` и `.zcode/skills/requirement-add/`.

### Requirement: Делегирование навыка formular

**Reason**: навык переименован в `requirement-add`.
**Migration**: требование «Делегирование навыка requirement-add» capability
`requirement-add-operation`; схема предмета `{YYYYMMDDHHMMSS}-{slug}` и делегирование
`/backlog:backlog-generate` → `/backlog:backlog-run` не изменились.
