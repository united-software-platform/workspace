#!/bin/sh
# Сканирование проекта образом tldr по уровням: обзор, безопасность, качество, архитектура.
#
# Сканирование исполняется одноразовым контейнером docker run --rm: проект монтируется
# в /project только для чтения; каталоги из EXCLUDE (и всегда reports) перекрываются
# пустыми временными каталогами поверх монтирования, на хосте они не меняются. Отчёты
# пишутся в /reports — bind-mount каталога отчётов. Каждая команда пишет stdout в свой
# файл отчёта, stderr — в соседний .err, удаляемый, если пуст. Сбой одной команды
# не останавливает остальные.
#
# Использование: sh tools/tldr/scan.sh <путь к проекту> [каталог отчётов]
#   каталог отчётов по умолчанию — reports/<имя проекта> в текущем каталоге
# Переменные окружения:
#   TLDR_IMAGE — образ, по умолчанию ghcr.io/united-software-platform/tldr-code:latest
#   EXCLUDE    — каталоги проекта через пробел, скрываемые от анализа, по умолчанию "vendor public";
#                каталог reports добавляется к скрываемым всегда
#   EXT        — расширение для дерева файлов вида .php, по умолчанию .php
# Коды возврата: 0 — все команды отработали, 1 — часть команд завершилась ошибкой,
#                2 — ошибка вызова или окружения (включая «нет docker» и «контейнер
#                не завершился за отведённое время»).

set -u

target="${1:-}"
if [ -z "$target" ]; then
    echo "usage: sh tools/tldr/scan.sh <project-path> [report-dir]" >&2
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
exclude="${EXCLUDE:-vendor public} reports"
ext="${EXT:-.php}"

# EXT вписывается в команды контейнера: допускаются только точка и буквоцифры, иначе отказ
if ! printf '%s' "$ext" | grep -qE '^\.[A-Za-z0-9]+$'; then
    echo "error: EXT must look like .php — dot, letters or digits only, got: $ext" >&2
    exit 2
fi

mkdir -p "$out" || exit 2
out=$(cd "$out" && pwd) || exit 2

uid=$(id -u)
gid=$(id -g)

echo "project: $target"
echo "reports: $out"
echo "image:   $image"
echo

# Скрываемые каталоги: перекрываются пустыми временными каталогами поверх /project.
# Перекрывается только существующий каталог; reports скрывается всегда
cleanup=""
mounts=""
hide_no=0
for dir in $exclude; do
    if [ -d "$target/$dir" ]; then
        hide_no=$((hide_no + 1))
        hide=$(mktemp -d) || exit 2
        cleanup="$cleanup $hide"
        mounts="$mounts -v \"$hide:/project/$dir:ro\""
        echo "exclude: $dir"
    else
        echo "exclude: $dir — not found, skipped"
    fi
done
trap 'for d in $cleanup; do rmdir "$d" 2>/dev/null || rm -rf "$d"; done' EXIT INT TERM

# Скрипт контейнера: те же команды tldr, отчёты — в /reports; статусные строки идут в stdout
pod_script='set -u
cd /project || exit 2
total=0
failures=0
run() {
    report="$1"
    shift
    total=$((total + 1))
    started=$(date +%s)
    if "$@" > "/reports/$report" 2> "/reports/$report.err"; then
        status="ok  "
    else
        status="FAIL"
        failures=$((failures + 1))
    fi
    [ -s "/reports/$report.err" ] || rm -f "/reports/$report.err"
    printf "%s %-24s %4ss  tldr %s\n" "$status" "$report" "$(( $(date +%s) - started ))" "$*"
}
echo "# 1. Обзор (L1, метрики)"
run 01-tree.json       tree . -e "$EXT"
run 02-loc.json        loc . --by-dir
run 03-structure.json  structure .
run 04-health.json     health .
echo "# 2. Безопасность"
run 10-secure.json     secure .
run 11-vuln.json       vuln .
run 12-api-check.json  api-check .
echo "# 3. Качество и горячие точки"'

if [ -d "$target/.git" ]; then
    pod_script="$pod_script
run 20-hotspots.json hotspots .
run 21-churn.json    churn ."
else
    pod_script="$pod_script
echo \"skip hotspots, churn — no .git in project\""
fi

pod_script="$pod_script
run 22-cognitive.json  cognitive . --threshold 15
run 23-smells.json     smells .
run 24-clones.json     clones .
run 25-debt.json       debt .
echo \"# 4. Архитектура (L2, паттерны)\"
run 30-calls.json      calls .
run 31-hubs.json       hubs . --top 20
run 32-inheritance.json inheritance .
run 33-coupling.json   coupling .
run 34-dead.json       dead .
echo
echo \"\$((total - failures))/\$total commands succeeded, reports in /reports\"
[ \"\$failures\" -eq 0 ]"

# Контейнер исполняется от uid/gid хоста, чтобы отчёты принадлежали пользователю;
# предел 1800s страхует от зависших команд сканирования
status=0
# shellcheck disable=SC2086
timeout 1800 docker run --rm \
    --user "$uid:$gid" \
    -e "EXT=$ext" \
    -v "$target:/project:ro" \
    -v "$out:/reports" \
    $mounts \
    "$image" /bin/sh -c "$pod_script" || status=$?

case "$status" in
    0)
        exit 0
        ;;
    1)
        echo "see *.err next to failed reports" >&2
        exit 1
        ;;
    124|137)
        echo "error: scan container did not finish in 1800s" >&2
        exit 2
        ;;
    *)
        echo "error: scan container failed with exit code $status" >&2
        exit 2
        ;;
esac
