#!/bin/sh
# Дописать в .env переменные Liquibase Forge (FORGE_*, LBFR_*) из .env.example, которых в .env
# ещё нет. Заданные пользователем значения не трогаются, повторный запуск ничего не меняет.
#
# Исключение — префикс имён контейнеров LBFR_CONTAINER_PREFIX: в шаблоне он пуст намеренно,
# общее значение дало бы всем проектам на хосте одни и те же имена контейнеров. Пустой или
# отсутствующий префикс выводится из имени корня проекта; из него не выйдет префикса — отказ
# до любой записи.
set -eu

PREFIX_NAME=LBFR_CONTAINER_PREFIX

if [ ! -f .env ]; then
	echo "Ошибка: нет файла .env — сначала выполните make init" >&2
	exit 1
fi

prefix=$(sed -n "s/^${PREFIX_NAME}=//p" .env | tail -n 1)
prefix_line=""
if [ -z "$prefix" ]; then
	# Нижний регистр, всё вне a-z0-9 — дефис, дефисы по краям отброшены. LC_ALL=C: диапазоны
	# a-z и A-Z — только латиница, многобайтные символы целиком уходят в дефисы
	prefix=$(basename "$(pwd)" | LC_ALL=C tr 'A-Z' 'a-z' \
		| LC_ALL=C sed -e 's/[^a-z0-9][^a-z0-9]*/-/g' -e 's/^-*//' -e 's/-*$//')
	if [ -z "$prefix" ]; then
		echo "Ошибка: из имени каталога «$(basename "$(pwd)")» не выводится $PREFIX_NAME —" \
			"задайте его в .env вручную: строчные латинские буквы, цифры и дефис" >&2
		exit 1
	fi
	prefix_line="${PREFIX_NAME}=${prefix}"
fi

missing=""
while IFS= read -r line; do
	[ -n "$line" ] || continue
	name=${line%%=*}
	[ "$name" != "$PREFIX_NAME" ] || continue
	grep -q "^${name}=" .env || missing="${missing}${line}
"
done <<LINES
$(grep -E '^(FORGE|LBFR)_[A-Z0-9_]*=' .env.example)
LINES

# Пустая строка префикса заменяется на месте — одной строкой, без дубля; отсутствующая
# дописывается вместе с остальными переменными
if [ -n "$prefix_line" ] && grep -q "^${PREFIX_NAME}=" .env; then
	tmp=$(mktemp)
	awk -v line="$prefix_line" -v name="$PREFIX_NAME" '
		index($0, name "=") == 1 { if (!done) print line; done = 1; next }
		{ print }
	' .env > "$tmp"
	# Перезапись через cat сохраняет права и владельца .env
	cat "$tmp" > .env
	rm -f "$tmp"
	echo "В .env задан префикс контейнеров: $prefix_line"
elif [ -n "$prefix_line" ]; then
	missing="${missing}${prefix_line}
"
fi

if [ -z "$missing" ]; then
	[ -n "$prefix_line" ] || echo "В .env уже есть все переменные Liquibase Forge"
	exit 0
fi

# Последняя строка .env может быть без перевода строки: дописанное не должно склеиться с ней
[ -z "$(tail -c 1 .env)" ] || echo >> .env
printf '\n# Liquibase Forge: добавлено make forge-env-sync из .env.example\n%s' "$missing" >> .env
echo "В .env добавлены переменные:"
printf '%s' "$missing" | sed 's/=.*//; s/^/  /'
