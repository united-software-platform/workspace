#!/bin/sh
# Сканирование проекта образом tldr по уровням: обзор, безопасность, качество, архитектура.
#
# Сканирование исполняется Job'ом в локальном кластере k3s: проект монтируется в /project
# hostPath'ом только для чтения; каталоги из EXCLUDE перекрываются пустыми tmpfs (emptyDir
# c medium: Memory) поверх монтирования, на хосте они не меняются. Отчёты пишутся в /reports —
# hostPath каталога отчётов. Каждая команда пишет stdout в свой файл отчёта, stderr — в соседний
# .err, удаляемый, если пуст. Сбой одной команды не останавливает остальные.
#
# Использование: sh tools/tldr/scan.sh <путь к проекту> [каталог отчётов]
#   каталог отчётов по умолчанию — reports/<имя проекта> в текущем каталоге
# Переменные окружения:
#   TLDR_IMAGE — образ, по умолчанию ghcr.io/united-software-platform/tldr-code:latest
#   EXCLUDE    — каталоги проекта через пробел, скрываемые от анализа, по умолчанию "vendor public"
#   EXT        — расширение для дерева файлов вида .php, по умолчанию .php
# Коды возврата: 0 — все команды отработали, 1 — часть команд завершилась ошибкой,
#                2 — ошибка вызова или окружения (включая «нет kubectl» и «Job не завершился»).

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
if ! command -v kubectl >/dev/null 2>&1; then
    echo "error: kubectl not found in PATH" >&2
    exit 2
fi

target=$(cd "$target" && pwd) || exit 2
out="${2:-reports/$(basename "$target")}"
image="${TLDR_IMAGE:-ghcr.io/united-software-platform/tldr-code:latest}"
exclude="${EXCLUDE:-vendor public}"
ext="${EXT:-.php}"

# EXT вписывается в скрипт Job'а: допускаются только точка и буквоцифры, иначе отказ
if ! printf '%s' "$ext" | grep -qE '^\.[A-Za-z0-9]+$'; then
    echo "error: EXT must look like .php — dot, letters or digits only, got: $ext" >&2
    exit 2
fi

mkdir -p "$out" || exit 2
out=$(cd "$out" && pwd) || exit 2

uid=$(id -u)
gid=$(id -g)
job="tldr-scan-$(date +%s)"

echo "project: $target"
echo "reports: $out"
echo "image:   $image"
echo "job:     $job"
echo

# Скрываемые каталоги: перекрываются пустыми tmpfs поверх /project. Перекрывается только
# существующий каталог: точки монтирования поверх отсутствующего hostPath не имеют смысла
vmounts=""
volumes=""
hide_no=0
for dir in $exclude; do
    if [ -d "$target/$dir" ]; then
        hide_no=$((hide_no + 1))
        vmounts="$vmounts
        - name: hide$hide_no
          mountPath: \"/project/$dir\""
        volumes="$volumes
      - name: hide$hide_no
        emptyDir:
          medium: Memory"
        echo "exclude: $dir"
    else
        echo "exclude: $dir — not found, skipped"
    fi
done

# Скрипт Job'а: те же команды tldr, отчёты — в /reports; статусные строки идут в stdout Job'а
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
run 01-tree.json       tree . -e "'"$ext"'"
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

manifest=$(mktemp) || exit 2
trap 'rm -f "$manifest"' EXIT INT TERM

{
    echo "apiVersion: batch/v1"
    echo "kind: Job"
    echo "metadata:"
    echo "  name: $job"
    echo "spec:"
    echo "  activeDeadlineSeconds: 1800"
    echo "  backoffLimit: 0"
    echo "  template:"
    echo "    spec:"
    echo "      restartPolicy: Never"
    echo "      securityContext:"
    echo "        runAsUser: $uid"
    echo "        runAsGroup: $gid"
    echo "      containers:"
    echo "      - name: tldr"
    echo "        image: \"$image\""
    echo "        command: [\"/bin/sh\", \"-c\"]"
    echo "        args:"
    echo "        - |"
    printf '%s\n' "$pod_script" | sed 's/^/          /'
    echo "        volumeMounts:"
    echo "        - name: project"
    echo "          mountPath: /project"
    echo "          readOnly: true"
    echo "        - name: reports"
    echo "          mountPath: /reports$vmounts"
    echo "      volumes:"
    echo "      - name: project"
    echo "        hostPath:"
    echo "          path: \"$target\""
    echo "          type: Directory"
    echo "      - name: reports"
    echo "        hostPath:"
    echo "          path: \"$out\""
    echo "          type: Directory$volumes"
} > "$manifest"

if ! kubectl apply -f "$manifest" >/dev/null 2>&1; then
    echo "error: kubectl apply failed — is the k3s cluster running?" >&2
    exit 2
fi

# Ожидание исхода Job'а: Complete или Failed; предел 1900s чуть больше дедлайна Job'а
outcome="unknown"
attempts=0
while [ "$attempts" -lt 190 ]; do
    if kubectl get job "$job" -o 'jsonpath={.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null | grep -q True; then
        outcome="complete"
        break
    fi
    if kubectl get job "$job" -o 'jsonpath={.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null | grep -q True; then
        outcome="failed"
        break
    fi
    attempts=$((attempts + 1))
    sleep 10
done

kubectl logs "job/$job" 2>&1
kubectl delete job "$job" --wait=false >/dev/null 2>&1

case "$outcome" in
    complete)
        exit 0
        ;;
    failed)
        echo "see *.err next to failed reports" >&2
        exit 1
        ;;
    *)
        echo "error: job $job did not finish in time" >&2
        exit 2
        ;;
esac
