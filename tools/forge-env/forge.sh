#!/bin/sh
# Запустить CLI forge из корня проекта одной командой в любом репозитории. В целевом проекте
# CLI — uv-подпроект tools/forge/: запуск по зафиксированному uv.lock без зависимостей
# разработки, а --project оставляет рабочим каталогом корень проекта, поэтому backlog/, .forge/
# и FORGE_ACCEPTED_DIR разрешаются от него. В репозитории forge CLI — сам корневой uv-проект.
# exec передаёт аргументы, stdout и код возврата CLI без изменений.
if [ -f tools/forge/pyproject.toml ]; then
	exec uv run --project tools/forge --frozen --no-dev forge "$@"
fi
exec uv run forge "$@"
