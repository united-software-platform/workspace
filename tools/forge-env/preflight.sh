#!/bin/sh
# Предварительная проверка make forge-env-up: имена контейнеров lbfr-db и lbfr-db-test и хостовый
# порт lbfr-db не заняты контейнером другого Compose-проекта. Имя контейнера уникально на весь
# Docker-хост, поэтому без проверки второй проект с forge получил бы от демона «Conflict» без
# подсказки, что менять. Контейнеры скрипт не запускает, не останавливает и не удаляет.
#
# Значения берутся из итоговой конфигурации Compose, а не из .env: так видны те же имена и порт,
# что подставит docker compose up. Коды возврата: 0 — конфликтов нет, 1 — есть конфликт,
# 2 — конфигурация Compose не разбирается.
set -eu

config=$(docker compose config --format json lbfr-db lbfr-db-test 2>/dev/null) || config=""
# Строки вида «project <имя>», «container <имя контейнера>», «port <хостовый порт>»
facts=$(printf '%s' "$config" | python3 -c '
import json, sys
config = json.load(sys.stdin)
print("project", config["name"])
for service in ("lbfr-db", "lbfr-db-test"):
    print("container", config["services"][service]["container_name"])
for port in config["services"]["lbfr-db"].get("ports") or []:
    if port.get("target") == 5432 and port.get("published"):
        print("port", port["published"])
' 2>/dev/null) || facts=""
project=$(printf '%s\n' "$facts" | awk '$1 == "project" { print $2 }')
if [ -z "$project" ]; then
	echo "Ошибка: конфигурация Compose не разбирается — выполните make forge-env-check" >&2
	exit 2
fi

FORMAT='{{.Names}}	{{.Label "com.docker.compose.project"}}	{{.Label "com.docker.compose.project.working_dir"}}'

# Контейнеры другого проекта из вывода docker ps: имя, проект и каталог через табуляцию.
# Контейнер вне Compose (без метки проекта) — тоже чужой
foreign() {
	awk -F '	' -v own="$project" -v want="${1:-}" '
		(want == "" || $1 == want) && $2 != own { print }
	'
}

# owner <контейнер> <проект> <каталог> — как назвать владельца в сообщении
owner() {
	if [ -n "$2" ]; then
		printf 'контейнером %s проекта %s (%s)' "$1" "$2" "${3:-каталог неизвестен}"
	else
		printf 'контейнером %s вне Compose' "$1"
	fi
}

status=0
for name in $(printf '%s\n' "$facts" | awk '$1 == "container" { print $2 }'); do
	found=$(docker ps -a --filter "name=^/${name}\$" --format "$FORMAT" | foreign "$name")
	[ -n "$found" ] || continue
	IFS='	' read -r cname cproject cdir <<FOUND
$found
FOUND
	echo "Ошибка: имя контейнера $name занято $(owner "$cname" "$cproject" "$cdir") —" \
		"задайте в .env другой LBFR_CONTAINER_PREFIX" >&2
	status=1
done

port=$(printf '%s\n' "$facts" | awk '$1 == "port" { print $2; exit }')
if [ -n "$port" ]; then
	found=$(docker ps --filter "publish=${port}" --format "$FORMAT" | foreign | head -n 1)
	if [ -n "$found" ]; then
		IFS='	' read -r cname cproject cdir <<FOUND
$found
FOUND
		echo "Ошибка: хостовый порт $port занят $(owner "$cname" "$cproject" "$cdir") —" \
			"задайте в .env другой FORGE_DB_HOST_PORT" >&2
		status=1
	fi
fi
exit "$status"
