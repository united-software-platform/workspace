"""Общий обход дерева узлов YAML для разборщиков файлов формата forge.

Стандартный `safe_load` молча берёт последнее значение повторного ключа, поэтому разборщики
получают дерево узлов загрузчиком `SafeLoader` и обходят его сами: так они видят повторы
и знают логический путь каждого значения.

Помощники не зависят ни от одного контекста: о нарушении они сообщают обратным вызовом
`report(ключ, код, сообщение)` с путём относительно проверяемого узла, а нарушение в терминах
своего контекста строит разборщик.
"""

from __future__ import annotations

from collections.abc import Callable

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

STR_TAG = "tag:yaml.org,2002:str"
INT_TAG = "tag:yaml.org,2002:int"
BOOL_TAG = "tag:yaml.org,2002:bool"
FLOAT_TAG = "tag:yaml.org,2002:float"
NULL_TAG = "tag:yaml.org,2002:null"
TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"

KIND_NAMES = {
    STR_TAG: "строка",
    INT_TAG: "целое число",
    BOOL_TAG: "логическое значение",
    FLOAT_TAG: "дробное число",
    NULL_TAG: "пустое значение",
    TIMESTAMP_TAG: "дата",
}

Report = Callable[[str, str, str], None]
"""Обратный вызов нарушения: ключ относительно узла (пустой — сам узел), код, сообщение."""


class YamlSyntaxError(Exception):
    """Текст не разбирается как YAML; сообщение называет строку и столбец, если они известны."""


def load_single_node(loader: yaml.SafeLoader) -> Node | None:
    """Корневой узел единственного документа; пустой документ — `None`.

    Синтаксическая ошибка и несколько документов — `YamlSyntaxError`.
    """
    try:
        return loader.get_single_node()
    except yaml.MarkedYAMLError as error:
        raise YamlSyntaxError(_syntax_message(error)) from None
    except yaml.YAMLError as error:
        raise YamlSyntaxError(f"файл не разбирается как YAML: {error}") from None


def _syntax_message(error: yaml.MarkedYAMLError) -> str:
    mark = error.problem_mark
    problem = error.problem or "ошибка синтаксиса"
    if mark is None:
        return f"файл не разбирается как YAML: {problem}"
    position = f"строка {mark.line + 1}, столбец {mark.column + 1}"
    return f"файл не разбирается как YAML: {position}: {problem}"


def mapping_fields(
    node: Node, required: tuple[str, ...], optional: tuple[str, ...], report: Report
) -> dict[str, Node] | None:
    """Первое вхождение каждого поля отображения; `None`, если узел — не отображение.

    Неизвестные, повторные и отсутствующие поля — нарушения `unknown_field`, `duplicate_key`
    и `missing_field` с ключом поля; узел другого вида — `wrong_kind` с пустым ключом.
    """
    if not isinstance(node, MappingNode):
        report(
            "",
            "wrong_kind",
            wrong_kind_message(node, "отображение с полями " + ", ".join(required)),
        )
        return None
    allowed = required + optional
    nodes: dict[str, Node] = {}
    for key_node, value_node in node.value:
        key = key_node.value if isinstance(key_node, ScalarNode) else "?"
        if key in nodes:
            report(key, "duplicate_key", f"ключ {key} повторён, значения не объединяются")
        elif key not in allowed or key_node.tag != STR_TAG:
            report(
                key,
                "unknown_field",
                f"поле {key} не входит в формат, допустимы: {', '.join(allowed)}",
            )
        else:
            nodes[key] = value_node
    for field in required:
        if field not in nodes:
            report(field, "missing_field", f"нет обязательного поля {field}")
    return nodes


def string_value(node: Node) -> str | None:
    """Значение строкового скаляра; узел другого вида — `None`."""
    if node.tag == STR_TAG and isinstance(node, ScalarNode):
        return str(node.value)
    return None


def integer_value(loader: yaml.SafeLoader, node: Node) -> int | None:
    """Значение целого скаляра; узел другого вида или неразборчивое целое — `None`."""
    if node.tag != INT_TAG:
        return None
    try:
        value = loader.construct_object(node)
    except (yaml.YAMLError, ValueError):
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def wrong_kind_message(node: Node, expected: str) -> str:
    """Сообщение о значении не того вида; скаляру на месте строки — совет о кавычках."""
    message = f"ожидалось: {expected}; получено: {describe(node)}"
    if expected == "строка" and node.tag != STR_TAG and isinstance(node, ScalarNode):
        message += f"; чтобы {node.value!r} читалось как строка, возьмите его в кавычки"
    return message


def describe(node: Node) -> str:
    """Вид и значение узла для сообщения: `отображение`, `список`, `целое число '10'`."""
    if isinstance(node, MappingNode):
        return "отображение"
    if isinstance(node, SequenceNode):
        return "список"
    kind = KIND_NAMES.get(node.tag, f"значение с тегом {node.tag}")
    return f"{kind} {node.value!r}"
