#!/bin/sh
# Сканирование стороннего проекта образом tldr по уровням: обзор, безопасность, качество, архитектура.
#
# Проект монтируется в /project только для чтения; каталоги из EXCLUDE перекрываются пустыми tmpfs
# внутри контейнера, на хосте они не меняются. Каждая команда пишет stdout в свой файл отчёта,
# stderr — в соседний .err, который удаляется, если пуст. Сбой одной команды не останавливает остальные.
#
# Использование: sh scripts/tldr-scan.sh <путь к проекту> [каталог отчётов]
#   каталог отчётов по умолчанию — reports/<имя проекта> в текущем каталоге
# Переменные окружения:
#   TLDR_IMAGE — образ, по умолчанию ghcr.io/united-software-platform/tldr-code:latest
#   EXCLUDE    — каталоги проекта через пробел, скрываемые от анализа, по умолчанию "vendor public"
#   EXT        — расширение для дерева файлов, по умолчанию .php
# Коды возврата: 0 — все команды отработали, 1 — часть команд завершилась ошибкой,
#                2 — ошибка вызова или окружения.

set -u

target="${1:-}"
if [ -z "$target" ]; then
    echo "usage: sh scripts/tldr-scan.sh <project-path> [report-dir]" >&2
    exit 2
fi
if [ ! -d "$target" ]; then
    echo "error: project directory not found: $target" >&2
    exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker not found in PATH" >&2
    exit 2
fi

target=$(cd "$target" && pwd) || exit 2
out="${2:-reports/$(basename "$target")}"
image="${TLDR_IMAGE:-ghcr.io/united-software-platform/tldr-code:latest}"
exclude="${EXCLUDE:-vendor public}"
ext="${EXT:-.php}"

mkdir -p "$out" || exit 2
out=$(cd "$out" && pwd) || exit 2

# Образ загружается заранее: иначе прогресс docker pull попал бы в .err первой команды
if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "pulling $image"
    docker pull -q "$image" >/dev/null || exit 2
fi

# Перекрывается только существующий каталог: точку монтирования внутри :ro Docker создать не может
mounts=""
for dir in $exclude; do
    if [ -d "$target/$dir" ]; then
        mounts="$mounts --mount type=tmpfs,dst=/project/$dir"
        echo "exclude: $dir"
    else
        echo "exclude: $dir — not found, skipped"
    fi
done

me="$(id -u):$(id -g)"
failures=0
total=0

# run <файл отчёта> <аргументы tldr…>
run() {
    report="$1"
    shift
    total=$((total + 1))
    started=$(date +%s)
    # $mounts намеренно без кавычек: строка разбивается на отдельные ключи --mount
    # shellcheck disable=SC2086
    if docker run --rm -u "$me" -v "$target:/project:ro" $mounts "$image" "$@" \
        > "$out/$report" 2> "$out/$report.err"; then
        status="ok  "
    else
        status="FAIL"
        failures=$((failures + 1))
    fi
    [ -s "$out/$report.err" ] || rm -f "$out/$report.err"
    printf '%s %-24s %4ss  tldr %s\n' "$status" "$report" "$(( $(date +%s) - started ))" "$*"
}

echo "project: $target"
echo "reports: $out"
echo

echo "# 1. Обзор (L1, метрики)"
run 01-tree.json       tree . -e "$ext"
run 02-loc.json        loc . --by-dir
run 03-structure.json  structure .
run 04-health.json     health .

echo "# 2. Безопасность"
run 10-secure.json     secure .
run 11-vuln.json       vuln .
run 12-api-check.json  api-check .

echo "# 3. Качество и горячие точки"
if [ -d "$target/.git" ]; then
    run 20-hotspots.json hotspots .
    run 21-churn.json    churn .
else
    echo "skip hotspots, churn — no .git in project"
fi
run 22-cognitive.json  cognitive . --threshold 15
run 23-smells.json     smells .
run 24-clones.json     clones .
run 25-debt.json       debt .

echo "# 4. Архитектура (L2, паттерны)"
run 30-calls.json      calls .
run 31-hubs.json       hubs . --top 20
run 32-inheritance.json inheritance .
run 33-coupling.json   coupling .
run 34-dead.json       dead .

echo
echo "$((total - failures))/$total commands succeeded, reports in $out"
if [ "$failures" -gt 0 ]; then
    echo "see *.err next to failed reports" >&2
    exit 1
fi
