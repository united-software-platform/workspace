"""Подключение к PostgreSQL сервера целевой БД через `psycopg`."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import make_conninfo

from forge.shared.application.settings import DatabaseCredentials, DatabaseUnavailableError
from forge.shared.domain.target_database import TargetDatabase


class PostgresConnector:
    """Подключение к БД сервера целевой БД с учётными данными из окружения."""

    def __init__(self, credentials: DatabaseCredentials) -> None:
        self._credentials = credentials

    @contextmanager
    def connect(
        self, database: TargetDatabase, name: str | None = None
    ) -> Iterator[psycopg.Connection]:
        conninfo = make_conninfo(
            host=database.host,
            port=database.port,
            dbname=name or database.name,
            user=self._credentials.user,
            password=self._credentials.password,
        )
        try:
            with psycopg.connect(conninfo, autocommit=True, connect_timeout=10) as connection:
                yield connection
        except psycopg.Error as error:
            raise DatabaseUnavailableError(f"БД {database}: {error}") from None
