"""Сценарий отката неуспешной попытки с проверкой возврата схемы."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from forge.migration.application.changelog_storage import (
    ChangelogReaderInterface,
    ChangelogSummary,
    ChangelogUnreadableError,
    ConstraintRef,
    RowRef,
)
from forge.migration.application.database import (
    DatabaseRecreatorInterface,
    JournalEntry,
    JournalReaderInterface,
    RowProbeInterface,
    SchemaProbeInterface,
)
from forge.migration.application.liquibase_gateway import GatewayResult, LiquibaseGatewayInterface
from forge.migration.application.operation_record import OperationRecordReaderInterface
from forge.migration.application.rollback_attempt.input import RollbackAttemptInput
from forge.migration.application.rollback_attempt.output import CheckView, RollbackAttemptOutput
from forge.shared.application.result_writer import ResultWriterInterface
from forge.shared.application.settings import TargetDatabaseSettingsInterface
from forge.shared.domain.target_database import TargetDatabase

CHANGELOG = "changelog.yaml"
ROLLBACK_RESULT = "rollback.json"


class RollbackAttemptUseCaseInterface(Protocol):
    """Откатить попытку, если её модель не подтверждена."""

    def execute(self, input: RollbackAttemptInput) -> RollbackAttemptOutput: ...


@dataclass(frozen=True)
class RollbackDependencies:
    """Контракты, через которые сценарий отката обращается к окружению."""

    operations: OperationRecordReaderInterface
    settings: TargetDatabaseSettingsInterface
    changelogs: ChangelogReaderInterface
    journal: JournalReaderInterface
    schema: SchemaProbeInterface
    rows: RowProbeInterface
    recreator: DatabaseRecreatorInterface
    gateway: LiquibaseGatewayInterface
    writer: ResultWriterInterface


class RollbackAttemptUseCase:
    """После вердикта `success` ничего не меняет; иначе снимает применённые changeset попытки.

    Исключение — откат при отказе от операции (`discard`): подтверждённая попытка откатывается
    тем же порядком, что неуспешная, и в `rollback.json` пишется её фактический вердикт.

    Откат Liquibase выполняется, только если записи попытки — хвост журнала и changelog
    попытки на месте. Иначе, как и при ошибке Liquibase, целевая БД пересоздаётся и получает
    принятый changelog `accepted_master` — `master.yaml` корня принятого состояния. Затем
    проверяется возврат: добавленного changelog попытки в схеме нет, удалённое — снова есть;
    у changelog данных вставленных строк нет, удалённые есть, изменённые имеют прежние значения.
    Итог пишется в `rollback.json` каталога попытки. Ошибки окружения — исключения контрактов.
    """

    def __init__(self, dependencies: RollbackDependencies, accepted_master: str) -> None:
        self._deps = dependencies
        self._accepted_master = accepted_master

    def execute(self, input: RollbackAttemptInput) -> RollbackAttemptOutput:
        record = self._deps.operations.read(input.operation_path)
        verdict = record.verdict(input.attempt)
        if verdict == "success" and not input.discard:
            return RollbackAttemptOutput(None, input.attempt, verdict, "none", 0, None, (), True)

        target = self._deps.settings.target()
        self._deps.settings.allowlist().require(target)
        directory = record.attempt_directory(input.attempt)
        changelog_path = f"{directory}/{CHANGELOG}"
        summary = self._summary(changelog_path)
        logical = record.stamp.logical_file_path
        entries = self._deps.journal.entries(target)
        mine = [entry for entry in entries if entry.filename == logical]

        action, rolled_back = "none_applied", 0
        gateway: dict[str, Any] | None = None
        reason: str | None = None
        if mine:
            reason = _fallback_reason(entries, mine, summary)
            if reason is None:
                result = self._deps.gateway.rollback(changelog_path, target, len(mine))
                gateway = _gateway_document(result)
                if result.succeeded:
                    action, rolled_back = "liquibase_rollback", len(mine)
                else:
                    reason = "откат Liquibase завершился ошибкой"

        checks: list[CheckView] = []
        fallback: dict[str, Any] | None = None
        if reason is not None:
            action = "recreate_database"
            fallback, restored = self._recreate(target)
            checks.append(restored)
        checks += self._verify(target, logical, summary)
        verified = all(check.passed for check in checks)

        result_path = f"{directory}/{ROLLBACK_RESULT}"
        self._deps.writer.write(
            result_path,
            {
                "attempt": input.attempt,
                "verdict": verdict,
                "action": action,
                "rolled_back": rolled_back,
                "changelog": changelog_path,
                "database": str(target),
                "gateway": gateway,
                "fallback_reason": reason,
                "fallback": fallback,
                "checks": [
                    {"check": c.check, "passed": c.passed, "detail": c.detail} for c in checks
                ],
                "verified": verified,
            },
        )
        return RollbackAttemptOutput(
            result_path,
            input.attempt,
            verdict,
            action,
            rolled_back,
            reason,
            tuple(checks),
            verified,
        )

    def _summary(self, path: str) -> ChangelogSummary | None:
        try:
            return self._deps.changelogs.read(path)
        except ChangelogUnreadableError:
            return None

    def _recreate(self, target: TargetDatabase) -> tuple[dict[str, Any], CheckView]:
        # Перед удалением БД перечень тестовых проверяется ещё раз — вплотную к DROP DATABASE
        self._deps.settings.allowlist().require(target)
        self._deps.recreator.recreate(target)
        if not self._deps.changelogs.exists(self._accepted_master):
            detail = f"{self._accepted_master} нет: принятого состояния нет, БД оставлена пустой"
            return {"recreated": True, "master": None}, CheckView("accepted_restored", True, detail)
        result = self._deps.gateway.update(self._accepted_master, target)
        check = CheckView(
            "accepted_restored",
            result.succeeded,
            f"накат {self._accepted_master}: код {result.exit_code}",
        )
        return {"recreated": True, "master": _gateway_document(result)}, check

    def _verify(
        self, target: TargetDatabase, logical: str, summary: ChangelogSummary | None
    ) -> list[CheckView]:
        left = [e.id for e in self._deps.journal.entries(target) if e.filename == logical]
        checks = [
            CheckView(
                "journal_clean",
                not left,
                f"записей {logical} в журнале: {len(left)}"
                + (f" ({', '.join(left)})" if left else ""),
            )
        ]
        if summary is None:
            checks.append(
                CheckView(
                    "attempt_objects",
                    True,
                    "changelog попытки не найден: объекты попытки не проверены, проверен журнал",
                )
            )
            return checks
        for table in summary.tables:
            present = self._deps.schema.table_exists(target, table)
            checks.append(CheckView("table_absent", not present, f"таблица {table}"))
        for table, column in summary.columns:
            present = self._deps.schema.column_exists(target, table, column)
            checks.append(CheckView("column_absent", not present, f"колонка {table}.{column}"))
        for constraint in summary.constraints:
            present = self._constraint_exists(target, constraint)
            checks.append(
                CheckView(f"{constraint.kind}_absent", not present, _constraint_detail(constraint))
            )
        for table in summary.dropped_tables:
            present = self._deps.schema.table_exists(target, table)
            checks.append(CheckView("table_present", present, f"таблица {table}"))
        for table, column in summary.dropped_columns:
            present = self._deps.schema.column_exists(target, table, column)
            checks.append(CheckView("column_present", present, f"колонка {table}.{column}"))
        for constraint in summary.dropped_constraints:
            present = self._constraint_exists(target, constraint)
            checks.append(
                CheckView(f"{constraint.kind}_present", present, _constraint_detail(constraint))
            )
        for row in summary.inserted_rows:
            checks.append(self._row_check("row_absent", target, row, expected=0))
        for row in summary.updated_rows:
            checks.append(self._row_check("row_restored", target, row, expected=1))
        for row in summary.deleted_rows:
            checks.append(self._row_check("row_present", target, row, expected=1))
        return checks

    def _row_check(
        self, check: str, target: TargetDatabase, row: RowRef, expected: int
    ) -> CheckView:
        """Строка по условию на ключ и литералам отката: `0` — её нет, `1` — она на месте."""
        found = self._deps.rows.count_rows(target, row)
        detail = f"строка {row.table} WHERE {row.where}"
        if row.values:
            detail += " со значениями " + ", ".join(f"{c} = {v}" for c, v in row.values)
        return CheckView(check, found == expected, f"{detail}: найдено {found}")

    def _constraint_exists(self, target: TargetDatabase, constraint: ConstraintRef) -> bool:
        return self._deps.schema.constraint_exists(
            target, constraint.table, constraint.name, constraint.kind
        )


def _constraint_detail(constraint: ConstraintRef) -> str:
    kind = "внешний ключ" if constraint.kind == "foreign_key" else "набор уникальности"
    return f"{kind} {constraint.table}.{constraint.name}"


def _fallback_reason(
    entries: tuple[JournalEntry, ...], mine: list[JournalEntry], summary: ChangelogSummary | None
) -> str | None:
    """Причина запасного пути или `None`, если откат Liquibase применим."""
    if summary is None:
        return "changelog попытки не найден"
    tail = entries[-len(mine) :]
    if any(entry.filename != mine[0].filename for entry in tail):
        return "записи попытки не являются хвостом журнала"
    unknown = [entry.id for entry in mine if entry.id not in summary.changeset_ids]
    if unknown:
        return f"в журнале changeset, которых нет в changelog попытки: {', '.join(unknown)}"
    return None


def _gateway_document(result: GatewayResult) -> dict[str, Any]:
    return {
        "request_id": result.request_id,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
