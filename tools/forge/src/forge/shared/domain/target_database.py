"""Целевая БД и перечень тестовых БД, на которые разрешены накат и откат."""

from __future__ import annotations

from dataclasses import dataclass


class DatabaseNotAllowedError(Exception):
    """Целевая БД не входит в перечень тестовых: накат и откат запрещены."""


class InvalidAllowlistError(ValueError):
    """Запись перечня тестовых БД не в формате `хост:порт/имя`."""


@dataclass(frozen=True)
class TargetDatabase:
    """Адрес БД: хост, порт и имя."""

    host: str
    port: int
    name: str

    def __str__(self) -> str:
        return f"{self.host}:{self.port}/{self.name}"


@dataclass(frozen=True)
class AllowedDatabase:
    """Запись перечня: `None` вместо имени разрешает любую БД сервера."""

    host: str
    port: int
    name: str | None

    def admits(self, database: TargetDatabase) -> bool:
        return (
            self.host == database.host
            and self.port == database.port
            and (self.name is None or self.name == database.name)
        )


@dataclass(frozen=True)
class TestDatabaseAllowlist:
    """Перечень тестовых БД. Пустой перечень не допускает ни одной БД.

    Правила совпадают с проверкой шлюза Liquibase: команда проверяет адрес до обращения
    к раннеру, шлюз — повторно на хосте.
    """

    __test__ = False  # не тестовый класс, несмотря на префикс имени

    entries: tuple[AllowedDatabase, ...]

    def admits(self, database: TargetDatabase) -> bool:
        return any(entry.admits(database) for entry in self.entries)

    def require(self, database: TargetDatabase) -> None:
        """Пропустить БД из перечня; иначе `DatabaseNotAllowedError`."""
        if not self.entries:
            raise DatabaseNotAllowedError(
                "перечень тестовых БД FORGE_TEST_DB_ALLOWLIST пуст: БД не считается тестовой"
            )
        if not self.admits(database):
            raise DatabaseNotAllowedError(f"БД вне перечня тестовых: {database}")


def parse_allowlist(value: str | None) -> TestDatabaseAllowlist:
    """Разобрать `FORGE_TEST_DB_ALLOWLIST`: записи `хост:порт/имя` через запятую."""
    entries = [entry.strip() for entry in (value or "").split(",") if entry.strip()]
    return TestDatabaseAllowlist(tuple(_entry(entry) for entry in entries))


def _entry(entry: str) -> AllowedDatabase:
    server, slash, name = entry.rpartition("/")
    host, colon, port = server.rpartition(":")
    if not (slash and colon and host and name and port.isdigit()):
        raise InvalidAllowlistError(
            f"запись перечня тестовых БД не в формате хост:порт/имя: {entry}"
        )
    return AllowedDatabase(host, int(port), None if name == "*" else name)
