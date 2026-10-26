#!/bin/sh
# Проверить окружение Compose: версия 2.20+ (нужна для include:) и выбор файла kit'а —
# в конфигурации должны быть и сервис агента, и сервисы проекта.
set -eu

version=$(docker compose version --short)
version=${version#v}
major=${version%%.*}
rest=${version#*.}
minor=${rest%%.*}
if [ "$major" -lt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -lt 20 ]; }; then
	echo "Ошибка: Docker Compose $version, нужен 2.20 или новее для include:" >&2
	exit 1
fi
echo "Docker Compose $version"

services=$(docker compose --profile claude --profile tools config --services)
status=0
for service in claude lbfr-db lbfr-db-test lbfr-liquibase; do
	if printf '%s\n' "$services" | grep -qx "$service"; then
		echo "  сервис $service: есть"
	else
		echo "  сервис $service: НЕТ" >&2
		status=1
	fi
done
[ "$status" -eq 0 ] || echo "Ошибка: Compose выбрал не тот файл или include: не сработал" >&2

# Хостовый порт и имя контейнера lbfr-db приходят из .env без значений по умолчанию: пустая
# переменная не должна молча дать БД без публикации, со случайным портом или с именем «-lbfr-db».
# Значения читаются из итоговой конфигурации Compose одним разбором; ошибка разбора — тоже отказ
config=$(docker compose config --format json lbfr-db 2>/dev/null) || config=""
published=$(printf '%s' "$config" | python3 -c '
import json, sys
ports = json.load(sys.stdin)["services"]["lbfr-db"].get("ports") or []
print(next((str(p.get("published") or "") for p in ports if p.get("target") == 5432), ""))
' 2>/dev/null) || published=""
if [ -n "$published" ]; then
	echo "  порт lbfr-db на хосте: $published"
else
	echo "  порт lbfr-db на хосте: НЕ ЗАДАН" >&2
	echo "Ошибка: в .env нет значения FORGE_DB_HOST_PORT — выполните make forge-env-sync" >&2
	status=1
fi

# Префикс — то, что стоит перед «-lbfr-db» в имени контейнера: так проверяется значение, которое
# действительно подставил Compose, включая переопределение из окружения
container=$(printf '%s' "$config" | python3 -c '
import json, sys
print(json.load(sys.stdin)["services"]["lbfr-db"].get("container_name") or "")
' 2>/dev/null) || container=""
prefix=${container%-lbfr-db}
if [ -z "$prefix" ] || [ "$prefix" = "$container" ]; then
	echo "  контейнер lbfr-db: префикс НЕ ЗАДАН" >&2
	echo "Ошибка: в .env нет значения LBFR_CONTAINER_PREFIX — выполните make forge-env-sync" >&2
	status=1
elif printf '%s\n' "$prefix" | LC_ALL=C grep -qx '[a-z0-9][a-z0-9-]*'; then
	echo "  контейнер lbfr-db: $container"
else
	echo "  контейнер lbfr-db: НЕДОПУСТИМЫЙ ПРЕФИКС «$prefix»" >&2
	echo "Ошибка: LBFR_CONTAINER_PREFIX — строчные латинские буквы, цифры и дефис, первый символ —" \
		"буква или цифра" >&2
	status=1
fi
exit "$status"
