#!/usr/bin/env python3
"""Снимок расхода токенов текущей сессии Claude Code.

Читает стенограмму проекта, суммирует usage всех ответов модели и печатает
накопленные счётчики. Разница двух снимков = расход за интервал между ними:
например, до и после операции forge. Каталог стенограмм определяется из текущего
каталога (/app -> ~/.claude/projects/-app) и переопределяется ключом --dir.
"""

import argparse
import glob
import json
import os
import time


def transcript_dir(raw: str | None) -> str:
    if raw:
        return os.path.expanduser(raw)
    slug = os.getcwd().replace("/", "-").replace(".", "-")
    return os.path.join(os.path.expanduser("~/.claude/projects"), slug)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", help="каталог стенограмм вместо вычисленного из cwd")
    args = parser.parse_args()

    directory = transcript_dir(args.dir)
    files = glob.glob(os.path.join(directory, "*.jsonl"))
    if not files:
        raise SystemExit(f"Стенограмм нет в {directory}")

    path = max(files, key=os.path.getmtime)
    calls = 0
    sidechain_calls = 0
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            calls += 1
            if record.get("isSidechain"):
                sidechain_calls += 1
            totals["input"] += usage.get("input_tokens") or 0
            totals["output"] += usage.get("output_tokens") or 0
            totals["cache_read"] += usage.get("cache_read_input_tokens") or 0
            totals["cache_creation"] += usage.get("cache_creation_input_tokens") or 0

    billed_input = totals["input"] + totals["cache_read"] + totals["cache_creation"]
    print(f"session file : {os.path.basename(path)}")
    print(f"snapshot time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"api calls    : {calls} (sidechain: {sidechain_calls})")
    print(f"input        : {totals['input']}")
    print(f"cache_read   : {totals['cache_read']}")
    print(f"cache_new    : {totals['cache_creation']}")
    print(f"output       : {totals['output']}")
    print(f"input_total  : {billed_input}  (input + cache_read + cache_new)")
    print(f"all_tokens   : {billed_input + totals['output']}")


if __name__ == "__main__":
    main()
