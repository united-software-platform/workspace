"""Точка входа CLI доменной раскладки.

Коды возврата: 0 — цель достигнута, включая пропуск как выполненной ранее;
1 — состояние не позволяет выполнить прогон (непринятый прогон, невычислимый
путь, коллизия имён, занятый целевой путь); 2 — ошибка вызова или окружения
(файлы прогона или таксономии не найдены, неразборчивые контракты).
"""

import argparse
import sys
from pathlib import Path

from layout.application.layout import LayoutEnvironmentError, LayoutStateError, layout

#: Выгрузка таксономии классификатора, поставляемая рядом с утилитой.
_TAXONOMY_DIR = Path(__file__).resolve().parents[4] / "classifier" / "taxonomy"


def build_parser() -> argparse.ArgumentParser:
    """Собрать парсер аргументов CLI."""
    parser = argparse.ArgumentParser(
        prog="layout",
        description=(
            "Доменная раскладка проекта: каталог принятого прогона classify "
            "→ дерево projects/<слаг L1>/<слаг L2>/<проект> и реестр происхождения"
        ),
    )
    parser.add_argument("run_dir", help="каталог беклога прогона classify")
    parser.add_argument("--root", type=Path, required=True, help="корень рабочего пространства")
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=None,
        help="каталог выгрузки таксономии (по умолчанию — выгрузка классификатора)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Исполнить CLI-прогон раскладки."""
    args = build_parser().parse_args(argv)
    try:
        result = layout(Path(args.run_dir), args.root, args.taxonomy or _TAXONOMY_DIR)
    except LayoutStateError as exc:
        print(f"состояние не позволяет выполнить прогон: {exc}", file=sys.stderr)
        return 1
    except LayoutEnvironmentError as exc:
        print(f"ошибка окружения: {exc}", file=sys.stderr)
        return 2
    directory = "каталог создан" if result.created else "каталог существует — выполнено ранее"
    registry = "запись реестра обновлена" if result.registry_updated else "запись реестра актуальна"
    print(f"{result.path}\n{directory}; {registry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
