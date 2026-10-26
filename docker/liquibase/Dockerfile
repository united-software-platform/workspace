# check=skip=InvalidDefaultArgInFrom
# Директива выше снимает предупреждение BuildKit: базовый образ намеренно приходит только
# аргументом сборки из .env, умолчания в Dockerfile нет, чтобы версия не жила в двух местах.
# Образ Liquibase для шлюза Liquibase Forge.
# Начиная с 5.0 официальный образ Liquibase не содержит драйверов БД: драйвер PostgreSQL
# добавляется менеджером пакетов lpm. Версии приходят аргументами сборки из .env.
ARG LIQUIBASE_BASE_IMAGE
FROM ${LIQUIBASE_BASE_IMAGE}

ARG POSTGRESQL_DRIVER_VERSION

# lpm update обновляет перечень пакетов, чтобы закреплённая версия драйвера была известна lpm.
# Образ остаётся под пользователем liquibase базового образа, не под root [DOCK-012]
RUN lpm update && lpm add "postgresql@${POSTGRESQL_DRIVER_VERSION}" --global
