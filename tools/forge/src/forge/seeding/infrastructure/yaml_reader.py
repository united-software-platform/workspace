"""Чтение файла seed в YAML и проверка его структуры.

Дерево узлов обходится общими помощниками `yaml_nodes`: так разборщик видит повторные ключи
и знает логический путь каждого значения (`tables[0].rows[1].code`).

Здесь проверяется только структура: корень, поля таблиц, вид `rows` и строк, повторы ключей.
Значения не приводятся к типу — тип колонки известен только по модели: каждое значение
попадает в черновик видом скаляра и текстом. Текст целого и логического значения приводится
к канонической записи (`0x0A` → `10`, `yes` → `true`), чтобы домену не разбирать грамматику
YAML; строки, даты и дробные числа идут текстом как записаны.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from forge.modeling.domain.violation import Violation, join_path
from forge.seeding.application.seed_reading import (
    SeedNotFoundError,
    SeedReading,
    SeedUnreadableError,
)
from forge.seeding.domain.draft import RawValue, RowDraft, ScalarKind, SeedDraft, SeedTableDraft
from forge.shared.infrastructure.yaml_nodes import (
    BOOL_TAG,
    FLOAT_TAG,
    INT_TAG,
    NULL_TAG,
    STR_TAG,
    TIMESTAMP_TAG,
    YamlSyntaxError,
    describe,
    integer_value,
    load_single_node,
    mapping_fields,
    string_value,
    wrong_kind_message,
)

FORMAT_VERSION = 1

_ROOT_FIELDS = ("version", "tables")
_TABLE_FIELDS = ("name", "rows")
_TEXT_KINDS = {
    STR_TAG: ScalarKind.STRING,
    FLOAT_TAG: ScalarKind.FLOAT,
    NULL_TAG: ScalarKind.NULL,
    TIMESTAMP_TAG: ScalarKind.TIMESTAMP,
}


class YamlSeedDraftReader:
    """Реализация контракта чтения черновика seed для файла YAML."""

    def read(self, path: str) -> SeedReading:
        return parse_seed(_read_text(path))


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SeedNotFoundError(path) from None
    except IsADirectoryError:
        raise SeedUnreadableError(path, "это каталог") from None
    except UnicodeDecodeError as error:
        raise SeedUnreadableError(path, f"файл не в кодировке UTF-8: {error.reason}") from None
    except OSError as error:
        raise SeedUnreadableError(path, error.strerror or str(error)) from None


def parse_seed(text: str) -> SeedReading:
    """Разобрать текст seed: черновик из таблиц без структурных нарушений и все нарушения."""
    loader = yaml.SafeLoader(text)
    try:
        try:
            root = load_single_node(loader)
        except YamlSyntaxError as error:
            return SeedReading(SeedDraft(()), (Violation("", "yaml_syntax", str(error)),))
        return _Walker(loader).seed(root)
    finally:
        loader.dispose()


class _Walker:
    """Обход дерева узлов seed со сбором структурных нарушений по порядку документа."""

    def __init__(self, loader: yaml.SafeLoader) -> None:
        self._loader = loader
        self._violations: list[Violation] = []
        self._excluded: list[str] = []

    def seed(self, root: Node | None) -> SeedReading:
        if root is None:
            self._add(
                "", "wrong_kind", "файл seed пуст: ожидалось отображение с полями version и tables"
            )
            return self._result(())
        fields = self._mapping(root, "", _ROOT_FIELDS)
        if fields is None or not self._version(fields.get("version")):
            return self._result(())
        tables_node = fields.get("tables")
        if not isinstance(tables_node, SequenceNode):
            if tables_node is not None:
                self._wrong_kind(tables_node, "tables", "список таблиц")
            return self._result(())
        tables = [self._table(node, position) for position, node in enumerate(tables_node.value)]
        return self._result(tuple(table for table in tables if table is not None))

    def _result(self, tables: tuple[SeedTableDraft, ...]) -> SeedReading:
        return SeedReading(SeedDraft(tables, tuple(self._excluded)), tuple(self._violations))

    def _version(self, node: Node | None) -> bool:
        if node is None:
            return False
        if integer_value(self._loader, node) == FORMAT_VERSION:
            return True
        self._add(
            "version",
            "unsupported_version",
            f"поддерживается только version: {FORMAT_VERSION}, получено {describe(node)}",
        )
        return False

    def _table(self, node: Node, position: int) -> SeedTableDraft | None:
        path = f"tables[{position}]"
        before = len(self._violations)
        fields = self._mapping(node, path, _TABLE_FIELDS)
        if fields is None:
            return None
        name_node = fields.get("name")
        name = None if name_node is None else string_value(name_node)
        if name_node is not None and name is None:
            self._wrong_kind(name_node, join_path(path, "name"), "строка")
        rows = self._rows(fields.get("rows"), join_path(path, "rows"))
        if len(self._violations) > before or name is None or rows is None:
            if name is not None:
                self._excluded.append(name)
            return None
        return SeedTableDraft(position, name, rows)

    def _rows(self, node: Node | None, path: str) -> tuple[RowDraft, ...] | None:
        if node is None:
            return None
        if not isinstance(node, SequenceNode):
            self._wrong_kind(node, path, "список строк")
            return None
        rows = [self._row(item, f"{path}[{index}]") for index, item in enumerate(node.value)]
        if any(row is None for row in rows):
            return None
        return tuple(row for row in rows if row is not None)

    def _row(self, node: Node, path: str) -> RowDraft | None:
        if not isinstance(node, MappingNode):
            self._wrong_kind(node, path, "отображение «имя колонки → значение»")
            return None
        before = len(self._violations)
        values: dict[str, RawValue] = {}
        for key_node, value_node in node.value:
            key = string_value(key_node)
            if key is None:
                label = key_node.value if isinstance(key_node, ScalarNode) else "?"
                self._wrong_kind(key_node, join_path(path, str(label)), "строка")
            elif key in values:
                self._add(
                    join_path(path, key),
                    "duplicate_key",
                    f"ключ {key} повторён, значения не объединяются",
                )
            else:
                values[key] = self._value(value_node)
        if len(self._violations) > before:
            return None
        return RowDraft(tuple(values.items()))

    def _value(self, node: Node) -> RawValue:
        if isinstance(node, MappingNode | SequenceNode):
            return RawValue(ScalarKind.OTHER, describe(node))
        if node.tag == INT_TAG:
            value = integer_value(self._loader, node)
            if value is not None:
                return RawValue(ScalarKind.INTEGER, str(value))
        elif node.tag == BOOL_TAG:
            flag = bool(self._loader.construct_object(node))
            return RawValue(ScalarKind.BOOLEAN, "true" if flag else "false")
        elif node.tag in _TEXT_KINDS:
            return RawValue(_TEXT_KINDS[node.tag], str(node.value))
        return RawValue(ScalarKind.OTHER, describe(node))

    def _mapping(self, node: Node, path: str, required: tuple[str, ...]) -> dict[str, Node] | None:
        return mapping_fields(
            node,
            required,
            (),
            lambda key, code, message: self._add(join_path(path, key), code, message),
        )

    def _wrong_kind(self, node: Node, path: str, expected: str) -> None:
        self._add(path, "wrong_kind", wrong_kind_message(node, expected))

    def _add(self, path: str, code: str, message: str) -> None:
        self._violations.append(Violation(path, code, message))
