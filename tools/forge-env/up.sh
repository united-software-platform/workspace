#!/bin/sh
# Поднять окружение Liquibase Forge: загрузить образ PostgreSQL, собрать образ Liquibase
# с драйвером, запустить БД и дождаться их готовности. Повторный запуск безопасен.
set -eu

docker compose pull lbfr-db lbfr-db-test
docker compose --profile tools build lbfr-liquibase
# Имя контейнера или порт, занятые другим проектом, называются до запуска, а не ответом демона
sh tools/forge-env/preflight.sh
# Каталог данных lbfr-db создаётся здесь, а не демоном Docker при монтировании: иначе data/ и
# data/lbfr-db принадлежали бы root. Шаг стоит после проверки, чтобы отказ не оставлял следов
mkdir -p data/lbfr-db
docker compose up -d --wait lbfr-db lbfr-db-test
docker compose run --rm -T lbfr-liquibase --version
docker compose ps lbfr-db lbfr-db-test
