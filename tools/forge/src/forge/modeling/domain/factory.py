"""Фабрика модели данных: строит агрегат из черновика или сообщает все нарушения сразу."""

from __future__ import annotations

from dataclasses import replace

from forge.modeling.domain.column import Column
from forge.modeling.domain.column_type import ColumnType, parse_column_type
from forge.modeling.domain.data_model import DataModel, unknown_target
from forge.modeling.domain.draft import ColumnDraft, DataModelDraft, ForeignKeyDraft, TableDraft
from forge.modeling.domain.foreign_key import ForeignKey, duplicate_foreign_keys
from forge.modeling.domain.generation import Generation, parse_generation
from forge.modeling.domain.identifier import ColumnName, TableName
from forge.modeling.domain.primary_key import PrimaryKey
from forge.modeling.domain.table import Table
from forge.modeling.domain.unique_set import UniqueSet
from forge.modeling.domain.value_list import ValueList
from forge.modeling.domain.violation import ModelViolationError, Violation


class DataModelFactory:
    """Строит модель снизу вверх: колонки, ключ, наборы уникальности, таблицы, связи, агрегат.

    Нарушение одного элемента не останавливает проверку остальных: фабрика собирает нарушения
    каждого уровня с путями от корня файла модели и бросает их одним исключением. Колонка
    строится, только если корректны её имя и тип; инварианты таблицы проверяются, только если
    корректны все её колонки и ключ; набор уникальности с собственными нарушениями в них
    не участвует. Уникальность имён таблиц проверяется по всем таблицам с корректным именем.

    Внешние ключи проверяются вторым проходом, после всех таблиц: цель FK — собранная таблица.
    Таблица, не собранная из-за нарушений, целью не служит, и FK на неё не проверяется, пока
    таблица не исправлена. Нарушения FK идут после нарушений всех таблиц, по таблицам и FK
    в порядке модели.
    """

    def create(self, draft: DataModelDraft) -> DataModel:
        names: list[tuple[int, TableName]] = []
        built: list[tuple[TableDraft, Table]] = []
        violations: dict[int, list[Violation]] = {}
        for table_draft in draft.tables:
            table, table_violations, name = self._table(table_draft)
            violations[table_draft.position] = table_violations
            if name is not None:
                names.append((table_draft.position, name))
            if table is not None:
                built.append((table_draft, table))
        # Повтор имени — нарушение поля `name`, поэтому оно идёт первым среди нарушений таблицы
        for position, duplicate in DataModel.duplicate_names(names).items():
            violations[position].insert(0, duplicate)
        collected = [
            violation
            for table_draft in draft.tables
            for violation in violations[table_draft.position]
        ]
        tables, relation_violations = self._relations(draft, built)
        collected += relation_violations
        if collected:
            raise ModelViolationError(collected)
        return DataModel(tuple(tables))

    def _relations(
        self, draft: DataModelDraft, built: list[tuple[TableDraft, Table]]
    ) -> tuple[list[Table], list[Violation]]:
        """Второй проход: внешние ключи собранных таблиц против собранных таблиц.

        FK на таблицу, объявленную в файле, но не собранную, не проверяется и в модель
        не попадает: такая модель уже неполна из-за нарушений самой таблицы.
        """
        targets: dict[TableName, Table] = {}
        for _, table in built:
            targets.setdefault(table.name, table)
        declared = set(draft.excluded) | {table_draft.name for table_draft in draft.tables}
        tables: list[Table] = []
        violations: list[Violation] = []
        for table_draft, table in built:
            keys: list[ForeignKey] = []
            table_violations: list[Violation] = []
            valid: list[tuple[int, ForeignKey]] = []
            for index, key_draft in enumerate(table_draft.foreign_keys):
                key, found = self._foreign_key(key_draft, table, targets, declared)
                table_violations += [v.under(f"foreign_keys[{index}]") for v in found]
                if key is not None:
                    keys.append(key)
                    if not found:
                        valid.append((index, key))
            table_violations += duplicate_foreign_keys(valid).values()
            prefix = f"tables[{table_draft.position}]"
            violations += [violation.under(prefix) for violation in table_violations]
            if not table_violations:
                tables.append(replace(table, foreign_keys=tuple(keys)))
        return tables, violations

    def _foreign_key(
        self,
        draft: ForeignKeyDraft,
        source: Table,
        targets: dict[TableName, Table],
        declared: set[str],
    ) -> tuple[ForeignKey | None, list[Violation]]:
        """Внешний ключ и его нарушения с путями от FK; `None` — ключ не проверен до конца."""
        columns, violations = _names(draft.columns, "columns", "foreign_key_unknown_column")
        target_columns, target_violations = _names(
            draft.target_columns, "references.columns", "foreign_key_unknown_target_column"
        )
        target_name: TableName | None = None
        try:
            target_name = TableName(draft.table)
        except ModelViolationError:
            violations.append(unknown_target(draft.table))
        violations += target_violations
        if violations or target_name is None:
            return None, violations
        try:
            key = ForeignKey(tuple(columns), target_name, tuple(target_columns))
        except ModelViolationError as error:
            return None, list(error.violations)
        violations = key.source_violations(source)
        target = targets.get(target_name)
        if target is None:
            if draft.table in declared:
                return None, violations
            return None, [*violations, unknown_target(target_name)]
        violations += key.target_violations(source, target)
        return key, violations

    def _table(self, draft: TableDraft) -> tuple[Table | None, list[Violation], TableName | None]:
        prefix = f"tables[{draft.position}]"
        violations: list[Violation] = []

        name: TableName | None = None
        try:
            name = TableName(draft.name)
        except ModelViolationError as error:
            violations += error.under("name").violations

        columns: list[Column] = []
        for index, column_draft in enumerate(draft.columns):
            try:
                columns.append(self._column(column_draft))
            except ModelViolationError as error:
                violations += error.under(f"columns[{index}]").violations

        key, key_violations = self._primary_key(draft.primary_key)
        violations += key_violations

        unique: list[UniqueSet | None] = []
        for index, names in enumerate(draft.unique):
            unique_set, unique_violations = self._unique(names)
            violations += [violation.under(f"unique[{index}]") for violation in unique_violations]
            unique.append(unique_set)

        table: Table | None = None
        if key is not None and len(columns) == len(draft.columns):
            violations += Table.violations_of(columns, key, unique)
            built = tuple(unique_set for unique_set in unique if unique_set is not None)
            if name is not None and not violations:
                table = Table(name, tuple(columns), key, built)
        return table, [violation.under(prefix) for violation in violations], name

    @staticmethod
    def _column(draft: ColumnDraft) -> Column:
        violations: list[Violation] = []
        name: ColumnName | None = None
        try:
            name = ColumnName(draft.name)
        except ModelViolationError as error:
            violations += error.under("name").violations
        column_type: ColumnType | None = None
        try:
            column_type = parse_column_type(
                draft.type, length=draft.length, precision=draft.precision, scale=draft.scale
            )
        except ModelViolationError as error:
            violations += error.violations
        generated: Generation | None = None
        if draft.generated is not None:
            try:
                generated = parse_generation(draft.generated)
            except ModelViolationError as error:
                violations += error.violations
        check: ValueList | None = None
        if draft.check is not None:
            try:
                check = ValueList(draft.check)
            except ModelViolationError as error:
                violations += error.under("check").violations
        if column_type is not None:
            violations += Column.violations_of(column_type, draft.nullable, generated, check)
        if name is None or column_type is None or violations:
            raise ModelViolationError(violations)
        return Column(name, column_type, draft.nullable, generated, check)

    @staticmethod
    def _primary_key(names: tuple[str, ...]) -> tuple[PrimaryKey | None, list[Violation]]:
        columns, violations = _names(names, "primary_key", "primary_key_unknown_column")
        if violations:
            return None, violations
        try:
            return PrimaryKey(tuple(columns)), []
        except ModelViolationError as error:
            return None, list(error.under("primary_key").violations)

    @staticmethod
    def _unique(names: tuple[str, ...]) -> tuple[UniqueSet | None, list[Violation]]:
        """Набор уникальности и нарушения с путями от набора."""
        columns, violations = _names(names, "", "unique_unknown_column")
        if violations:
            return None, violations
        try:
            return UniqueSet(tuple(columns)), []
        except ModelViolationError as error:
            return None, list(error.violations)


def _names(
    values: tuple[str, ...], path: str, code: str
) -> tuple[list[ColumnName], list[Violation]]:
    """Имена колонок из списка; некорректное имя — ссылка на колонку, которой нет.

    Колонки с некорректным именем в таблице быть не может, поэтому такое имя сообщается кодом
    неизвестной колонки `code` с путём `<path>[N]`.
    """
    columns: list[ColumnName] = []
    violations: list[Violation] = []
    for position, value in enumerate(values):
        try:
            columns.append(ColumnName(value))
        except ModelViolationError:
            violations.append(
                Violation(f"{path}[{position}]", code, f"в таблице нет колонки {value!r}")
            )
    return columns, violations
