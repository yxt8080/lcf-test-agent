from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from local_test_agent.models import (
    DefectDraft,
    ExecutionResult,
    RequirementAnalysisDraft,
    RequirementHandoff,
    RequirementInput,
    RequirementRefinementRound,
    RequirementRecordDetail,
    RequirementRecordSummary,
    ScenarioDescriptor,
    TestAnalysisResult,
)
from local_test_agent.services.runtime_logger import RuntimeLogger


class LocalDatabase:
    """SQLite 持久化层。

    第一版优先保证单机可追溯，因此使用 JSON Blob + FTS 索引的轻量方案，
    避免在需求频繁变化时过早设计复杂关系模型。
    """

    def __init__(self, database_path: Path, runtime_logger: RuntimeLogger | None = None) -> None:
        self.database_path = database_path
        self.runtime_logger = runtime_logger
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    ACTIVE_REQUIREMENT_DRAFT_KEY = "active"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS requirements (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    requirement_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    generated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS requirement_handoffs (
                    requirement_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS requirement_refinements (
                    requirement_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS requirement_drafts (
                    draft_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    requirement_id TEXT NOT NULL,
                    module TEXT NOT NULL,
                    title TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS executions (
                    request_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS defect_drafts (
                    execution_request_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )
            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS scenario_fts USING fts5(
                        scenario_id,
                        module,
                        title,
                        content
                    );
                    """
                )
            except sqlite3.OperationalError:
                # 少数 Python 构建可能不带 FTS5，后续检索会自动降级为 LIKE。
                if self.runtime_logger is not None:
                    self.runtime_logger.warning(
                        "database.fts5.unavailable",
                        "当前 SQLite 不支持 FTS5，场景检索将降级为 LIKE。",
                        database_path=str(self.database_path),
                    )
                pass
        self._repair_legacy_requirement_links()

    def save_requirement(self, requirement: RequirementInput) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO requirements(id, title, payload, created_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (
                    requirement.id,
                    requirement.title,
                    requirement.model_dump_json(),
                    requirement.created_at.isoformat(),
                ),
            )

    def get_requirement(self, requirement_id: str) -> RequirementInput | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM requirements WHERE id = ?",
                (requirement_id,),
            ).fetchone()
        if not row:
            return None
        return RequirementInput.model_validate_json(row["payload"])

    def find_requirement_by_title(self, title: str) -> RequirementInput | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload FROM requirements
                WHERE title = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (title,),
            ).fetchone()
        if not row:
            return None
        return RequirementInput.model_validate_json(row["payload"])

    def save_analysis(self, analysis: TestAnalysisResult) -> None:
        with self._connect() as connection:
            self._save_analysis_payload(connection, analysis)
            self.upsert_scenarios(analysis.requirement_id, analysis.scenarios, connection=connection)

    def save_requirement_record(
        self,
        *,
        requirement: RequirementInput,
        analysis: TestAnalysisResult,
        handoff: RequirementHandoff,
        refinement_history: list[RequirementRefinementRound],
    ) -> None:
        with self._connect() as connection:
            # 正式确认保存时必须以单事务落库，避免需求、分析、场景处理方式和场景索引出现半成功状态。
            self._save_requirement_payload(connection, requirement)
            self._save_analysis_payload(connection, analysis)
            self._save_requirement_handoff_payload(connection, handoff)
            self._save_requirement_refinements_payload(
                connection,
                requirement_id=requirement.id,
                refinement_history=refinement_history,
            )
            self.delete_scenarios_by_requirement(requirement.id, connection=connection)
            self.upsert_scenarios(analysis.requirement_id, analysis.scenarios, connection=connection)

    def get_analysis(self, requirement_id: str) -> TestAnalysisResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM analyses WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
        if not row:
            return None
        return TestAnalysisResult.model_validate_json(row["payload"])

    def list_requirement_records(self) -> list[RequirementRecordSummary]:
        """返回需求分析记录摘要，供管理页快速浏览。

        管理页只需要轻量元信息，不直接把完整结构化结果一次性灌入列表，
        避免记录数量增加后页面初始化越来越重。
        """

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT r.payload AS requirement_payload,
                       a.payload AS analysis_payload,
                       h.payload AS handoff_payload
                FROM analyses a
                JOIN requirements r ON r.id = a.requirement_id
                LEFT JOIN requirement_handoffs h ON h.requirement_id = a.requirement_id
                ORDER BY a.generated_at DESC, r.created_at DESC
                """
            ).fetchall()

        records: list[RequirementRecordSummary] = []
        for row in rows:
            requirement = RequirementInput.model_validate_json(row["requirement_payload"])
            analysis = TestAnalysisResult.model_validate_json(row["analysis_payload"])
            handoff = (
                RequirementHandoff.model_validate_json(row["handoff_payload"])
                if row["handoff_payload"]
                else None
            )
            counts = self._resolve_requirement_handoff_counts(analysis, handoff)
            records.append(
                RequirementRecordSummary(
                    requirement_id=requirement.id,
                    title=requirement.title,
                    source=requirement.source,
                    created_at=requirement.created_at,
                    generated_at=analysis.generated_at,
                    summary=analysis.summary,
                    business_path=requirement.business_path,
                    scenario_count=len(analysis.scenarios),
                    automation_count=counts["automation"],
                    regression_count=counts["regression_only"],
                    deferred_count=counts["deferred"],
                    handoff_saved=handoff is not None,
                )
            )
        return records

    def get_requirement_record(self, requirement_id: str) -> RequirementRecordDetail | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT r.payload AS requirement_payload,
                       a.payload AS analysis_payload,
                       h.payload AS handoff_payload,
                       t.payload AS refinement_payload
                FROM analyses a
                JOIN requirements r ON r.id = a.requirement_id
                LEFT JOIN requirement_handoffs h ON h.requirement_id = a.requirement_id
                LEFT JOIN requirement_refinements t ON t.requirement_id = a.requirement_id
                WHERE a.requirement_id = ?
                """,
                (requirement_id,),
            ).fetchone()
        if not row:
            return None
        return RequirementRecordDetail(
            requirement=RequirementInput.model_validate_json(row["requirement_payload"]),
            analysis=TestAnalysisResult.model_validate_json(row["analysis_payload"]),
            handoff=(
                RequirementHandoff.model_validate_json(row["handoff_payload"])
                if row["handoff_payload"]
                else None
            ),
            refinement_history=self._load_requirement_refinement_rows(row["refinement_payload"]),
        )

    def delete_requirement_record(self, requirement_id: str) -> bool:
        with self._connect() as connection:
            scenario_rows = connection.execute(
                "SELECT scenario_id FROM scenarios WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchall()
            scenario_ids = [row["scenario_id"] for row in scenario_rows]
            if scenario_ids:
                placeholders = ", ".join("?" for _ in scenario_ids)
                try:
                    connection.execute(
                        f"DELETE FROM scenario_fts WHERE scenario_id IN ({placeholders})",
                        tuple(scenario_ids),
                    )
                except sqlite3.OperationalError:
                    # FTS5 可能不可用，删除主表即可。
                    pass
                connection.execute(
                    f"DELETE FROM scenarios WHERE scenario_id IN ({placeholders})",
                    tuple(scenario_ids),
                )
            connection.execute(
                "DELETE FROM requirement_handoffs WHERE requirement_id = ?",
                (requirement_id,),
            )
            connection.execute(
                "DELETE FROM requirement_refinements WHERE requirement_id = ?",
                (requirement_id,),
            )
            analysis_cursor = connection.execute(
                "DELETE FROM analyses WHERE requirement_id = ?",
                (requirement_id,),
            )
            connection.execute(
                "DELETE FROM requirements WHERE id = ?",
                (requirement_id,),
            )
            deleted = analysis_cursor.rowcount > 0
        return deleted

    def save_requirement_handoff(self, handoff: RequirementHandoff) -> None:
        with self._connect() as connection:
            self._save_requirement_handoff_payload(connection, handoff)

    def get_requirement_handoff(self, requirement_id: str) -> RequirementHandoff | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_handoffs WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
        if not row:
            return None
        return RequirementHandoff.model_validate_json(row["payload"])

    def save_requirement_refinements(
        self,
        *,
        requirement_id: str,
        refinement_history: list[RequirementRefinementRound],
    ) -> None:
        with self._connect() as connection:
            self._save_requirement_refinements_payload(
                connection,
                requirement_id=requirement_id,
                refinement_history=refinement_history,
            )

    def get_requirement_refinements(self, requirement_id: str) -> list[RequirementRefinementRound]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_refinements WHERE requirement_id = ?",
                (requirement_id,),
            ).fetchone()
        if not row:
            return []
        return self._load_requirement_refinement_rows(row["payload"])

    def save_active_requirement_draft(self, draft: RequirementAnalysisDraft) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO requirement_drafts(draft_key, payload, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(draft_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    self.ACTIVE_REQUIREMENT_DRAFT_KEY,
                    draft.model_dump_json(),
                    draft.last_updated_at.isoformat(),
                ),
            )

    def get_active_requirement_draft(self) -> RequirementAnalysisDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_drafts WHERE draft_key = ?",
                (self.ACTIVE_REQUIREMENT_DRAFT_KEY,),
            ).fetchone()
        if not row:
            return None
        return RequirementAnalysisDraft.model_validate_json(row["payload"])

    def delete_active_requirement_draft(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM requirement_drafts WHERE draft_key = ?",
                (self.ACTIVE_REQUIREMENT_DRAFT_KEY,),
            )

    def _resolve_requirement_handoff_counts(
        self,
        analysis: TestAnalysisResult,
        handoff: RequirementHandoff | None,
    ) -> dict[str, int]:
        if handoff is None:
            return {
                "automation": len(analysis.scenarios),
                "regression_only": 0,
                "deferred": 0,
            }

        counts = {
            "automation": 0,
            "regression_only": 0,
            "deferred": 0,
        }
        if handoff.scenario_decisions:
            for item in handoff.scenario_decisions:
                counts[item.status.value] += 1
            return counts

        counts["automation"] = len(handoff.selected_scenario_ids)
        return counts

    def upsert_scenarios(
        self,
        requirement_id: str,
        scenarios: list[ScenarioDescriptor],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if connection is not None:
            self._upsert_scenarios(connection, requirement_id, scenarios)
            return
        with self._connect() as current_connection:
            self._upsert_scenarios(current_connection, requirement_id, scenarios)

    def delete_scenarios_by_requirement(
        self,
        requirement_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if connection is not None:
            self._delete_scenarios_by_requirement(connection, requirement_id)
            return
        with self._connect() as current_connection:
            self._delete_scenarios_by_requirement(current_connection, requirement_id)

    def _save_requirement_payload(
        self,
        connection: sqlite3.Connection,
        requirement: RequirementInput,
    ) -> None:
        connection.execute(
            """
            INSERT INTO requirements(id, title, payload, created_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                payload = excluded.payload,
                created_at = excluded.created_at
            """,
            (
                requirement.id,
                requirement.title,
                requirement.model_dump_json(),
                requirement.created_at.isoformat(),
            ),
        )

    def _save_analysis_payload(
        self,
        connection: sqlite3.Connection,
        analysis: TestAnalysisResult,
    ) -> None:
        connection.execute(
            """
            INSERT INTO analyses(requirement_id, summary, payload, generated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(requirement_id) DO UPDATE SET
                summary = excluded.summary,
                payload = excluded.payload,
                generated_at = excluded.generated_at
            """,
            (
                analysis.requirement_id,
                analysis.summary,
                analysis.model_dump_json(),
                analysis.generated_at.isoformat(),
            ),
        )

    def _save_requirement_handoff_payload(
        self,
        connection: sqlite3.Connection,
        handoff: RequirementHandoff,
    ) -> None:
        connection.execute(
            """
            INSERT INTO requirement_handoffs(requirement_id, payload, saved_at)
            VALUES(?, ?, ?)
            ON CONFLICT(requirement_id) DO UPDATE SET
                payload = excluded.payload,
                saved_at = excluded.saved_at
            """,
            (
                handoff.requirement_id,
                handoff.model_dump_json(),
                handoff.saved_at.isoformat(),
            ),
        )

    def _save_requirement_refinements_payload(
        self,
        connection: sqlite3.Connection,
        *,
        requirement_id: str,
        refinement_history: list[RequirementRefinementRound],
    ) -> None:
        connection.execute(
            """
            INSERT INTO requirement_refinements(requirement_id, payload, saved_at)
            VALUES(?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(requirement_id) DO UPDATE SET
                payload = excluded.payload,
                saved_at = excluded.saved_at
            """,
            (
                requirement_id,
                json.dumps(
                    [item.model_dump(mode="json") for item in refinement_history],
                    ensure_ascii=False,
                ),
            ),
        )

    @staticmethod
    def _load_requirement_refinement_rows(payload: str | None) -> list[RequirementRefinementRound]:
        if not payload:
            return []
        items = json.loads(payload)
        return [RequirementRefinementRound.model_validate(item) for item in items]

    def _upsert_scenarios(
        self,
        connection: sqlite3.Connection,
        requirement_id: str,
        scenarios: list[ScenarioDescriptor],
    ) -> None:
        for scenario in scenarios:
            payload = scenario.model_dump_json()
            connection.execute(
                """
                INSERT INTO scenarios(scenario_id, requirement_id, module, title, payload)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(scenario_id) DO UPDATE SET
                    requirement_id = excluded.requirement_id,
                    module = excluded.module,
                    title = excluded.title,
                    payload = excluded.payload
                """,
                (
                    scenario.scenario_id,
                    requirement_id,
                    scenario.module,
                    scenario.title,
                    payload,
                ),
            )
            self._upsert_scenario_index(connection, scenario)

    def _delete_scenarios_by_requirement(
        self,
        connection: sqlite3.Connection,
        requirement_id: str,
    ) -> None:
        scenario_rows = connection.execute(
            "SELECT scenario_id FROM scenarios WHERE requirement_id = ?",
            (requirement_id,),
        ).fetchall()
        scenario_ids = [row["scenario_id"] for row in scenario_rows]
        if scenario_ids:
            placeholders = ", ".join("?" for _ in scenario_ids)
            try:
                connection.execute(
                    f"DELETE FROM scenario_fts WHERE scenario_id IN ({placeholders})",
                    tuple(scenario_ids),
                )
            except sqlite3.OperationalError:
                # FTS5 可能不可用，删除主表即可。
                pass
            connection.execute(
                f"DELETE FROM scenarios WHERE scenario_id IN ({placeholders})",
                tuple(scenario_ids),
            )

    def _repair_legacy_requirement_links(self) -> None:
        with self._connect() as connection:
            legacy_rows = connection.execute(
                """
                SELECT a.requirement_id AS legacy_requirement_key,
                       a.payload AS analysis_payload,
                       r.id AS normalized_requirement_id
                FROM analyses a
                JOIN requirements r ON r.title = a.requirement_id
                LEFT JOIN requirements linked ON linked.id = a.requirement_id
                WHERE linked.id IS NULL
                """
            ).fetchall()
            for row in legacy_rows:
                analysis = TestAnalysisResult.model_validate_json(row["analysis_payload"])
                normalized_requirement_id = row["normalized_requirement_id"]
                normalized_analysis = analysis.model_copy(update={"requirement_id": normalized_requirement_id})
                connection.execute(
                    """
                    UPDATE analyses
                    SET requirement_id = ?, payload = ?
                    WHERE requirement_id = ?
                    """,
                    (
                        normalized_requirement_id,
                        normalized_analysis.model_dump_json(),
                        row["legacy_requirement_key"],
                    ),
                )
                connection.execute(
                    """
                    UPDATE scenarios
                    SET requirement_id = ?
                    WHERE requirement_id = ?
                    """,
                    (
                        normalized_requirement_id,
                        row["legacy_requirement_key"],
                    ),
                )

            draft = self.get_active_requirement_draft()
            if draft is not None and draft.latest_analysis is not None:
                if draft.latest_analysis.requirement_id != draft.requirement.id:
                    normalized_draft = draft.model_copy(
                        update={
                            "latest_analysis": draft.latest_analysis.model_copy(
                                update={"requirement_id": draft.requirement.id}
                            )
                        }
                    )
                    connection.execute(
                        """
                        INSERT INTO requirement_drafts(draft_key, payload, updated_at)
                        VALUES(?, ?, ?)
                        ON CONFLICT(draft_key) DO UPDATE SET
                            payload = excluded.payload,
                            updated_at = excluded.updated_at
                        """,
                        (
                            self.ACTIVE_REQUIREMENT_DRAFT_KEY,
                            normalized_draft.model_dump_json(),
                            normalized_draft.last_updated_at.isoformat(),
                        ),
                    )

    def _upsert_scenario_index(
        self, connection: sqlite3.Connection, scenario: ScenarioDescriptor
    ) -> None:
        content = " ".join(
            [
                scenario.title,
                scenario.module,
                " ".join(scenario.tags),
                " ".join(scenario.steps),
                " ".join(scenario.assertions),
            ]
        )
        try:
            connection.execute(
                "DELETE FROM scenario_fts WHERE scenario_id = ?",
                (scenario.scenario_id,),
            )
            connection.execute(
                """
                INSERT INTO scenario_fts(scenario_id, module, title, content)
                VALUES(?, ?, ?, ?)
                """,
                (scenario.scenario_id, scenario.module, scenario.title, content),
            )
        except sqlite3.OperationalError:
            # FTS5 不可用时，由 search_scenarios 做降级。
            return

    def list_scenarios(self, scenario_ids: list[str] | None = None) -> list[ScenarioDescriptor]:
        query = "SELECT payload FROM scenarios"
        params: tuple[Any, ...] = ()
        if scenario_ids:
            placeholders = ", ".join("?" for _ in scenario_ids)
            query += f" WHERE scenario_id IN ({placeholders})"
            params = tuple(scenario_ids)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [ScenarioDescriptor.model_validate_json(row["payload"]) for row in rows]

    def search_scenarios(self, query: str, limit: int = 10) -> list[ScenarioDescriptor]:
        with self._connect() as connection:
            try:
                rows = connection.execute(
                    """
                    SELECT s.payload
                    FROM scenario_fts f
                    JOIN scenarios s ON s.scenario_id = f.scenario_id
                    WHERE scenario_fts MATCH ?
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                if self.runtime_logger is not None:
                    self.runtime_logger.warning(
                        "database.scenario_search.fallback",
                        "场景检索从 FTS5 降级为 LIKE。",
                        query=query,
                        limit=limit,
                    )
                like_query = f"%{query}%"
                rows = connection.execute(
                    """
                    SELECT payload
                    FROM scenarios
                    WHERE title LIKE ? OR module LIKE ? OR payload LIKE ?
                    LIMIT ?
                    """,
                    (like_query, like_query, like_query, limit),
                ).fetchall()
        return [ScenarioDescriptor.model_validate_json(row["payload"]) for row in rows]

    def save_execution_result(self, result: ExecutionResult) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO executions(request_id, status, payload, finished_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    status = excluded.status,
                    payload = excluded.payload,
                    finished_at = excluded.finished_at
                """,
                (
                    result.request_id,
                    result.status.value,
                    result.model_dump_json(),
                    result.finished_at.isoformat(),
                ),
            )

    def get_execution_result(self, request_id: str) -> ExecutionResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM executions WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if not row:
            return None
        return ExecutionResult.model_validate_json(row["payload"])

    def get_latest_execution_result(self) -> ExecutionResult | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM executions
                ORDER BY finished_at DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        return ExecutionResult.model_validate_json(row["payload"])

    def save_defect_draft(self, draft: DefectDraft) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO defect_drafts(execution_request_id, title, payload)
                VALUES(?, ?, ?)
                ON CONFLICT(execution_request_id) DO UPDATE SET
                    title = excluded.title,
                    payload = excluded.payload
                """,
                (
                    draft.execution_request_id,
                    draft.title,
                    draft.model_dump_json(),
                ),
            )

    def get_defect_draft(self, execution_request_id: str) -> DefectDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload FROM defect_drafts
                WHERE execution_request_id = ?
                """,
                (execution_request_id,),
            ).fetchone()
        if not row:
            return None
        return DefectDraft.model_validate_json(row["payload"])

    def export_state(self) -> dict[str, Any]:
        """便于调试和后续扩展 CLI。"""

        with self._connect() as connection:
            counts = {
                "requirements": connection.execute(
                    "SELECT COUNT(*) AS count FROM requirements"
                ).fetchone()["count"],
                "analyses": connection.execute(
                    "SELECT COUNT(*) AS count FROM analyses"
                ).fetchone()["count"],
                "requirement_handoffs": connection.execute(
                    "SELECT COUNT(*) AS count FROM requirement_handoffs"
                ).fetchone()["count"],
                "requirement_refinements": connection.execute(
                    "SELECT COUNT(*) AS count FROM requirement_refinements"
                ).fetchone()["count"],
                "requirement_drafts": connection.execute(
                    "SELECT COUNT(*) AS count FROM requirement_drafts"
                ).fetchone()["count"],
                "scenarios": connection.execute(
                    "SELECT COUNT(*) AS count FROM scenarios"
                ).fetchone()["count"],
                "executions": connection.execute(
                    "SELECT COUNT(*) AS count FROM executions"
                ).fetchone()["count"],
                "defect_drafts": connection.execute(
                    "SELECT COUNT(*) AS count FROM defect_drafts"
                ).fetchone()["count"],
            }
        return {"database_path": str(self.database_path), "counts": counts}
