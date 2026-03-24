from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from local_test_agent.models import ExecutionRequest, ExecutionResult, ExecutionStatus
from local_test_agent.services.runtime_logger import RuntimeLogger
from local_test_agent.store.database import LocalDatabase


class TestExecutor:
    def __init__(
        self,
        project_root: Path,
        database: LocalDatabase,
        runtime_logger: RuntimeLogger | None = None,
    ) -> None:
        self.project_root = project_root
        self.database = database
        self.runtime_logger = runtime_logger

    def run_tests(self, request: ExecutionRequest) -> ExecutionResult:
        started_at = datetime.now(UTC)
        scenarios = self.database.list_scenarios(request.scenario_ids)
        selectors = list(dict.fromkeys(item.test_selector for item in scenarios if item.test_selector))
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "pytest.execute.prepare",
                "已完成测试执行参数解析。",
                request_id=request.request_id,
                scenario_count=len(scenarios),
                selector_count=len(selectors),
                dry_run=request.dry_run,
            )

        if request.dry_run:
            if self.runtime_logger is not None:
                self.runtime_logger.info(
                    "pytest.execute.dry_run",
                    "当前为 dry-run，仅返回解析结果。",
                    request_id=request.request_id,
                    selectors=selectors,
                    pytest_args=request.pytest_args,
                )
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.SUCCESS,
                total=len(request.scenario_ids),
                passed=0,
                failed=0,
                skipped=0,
                summary="Dry-run 模式未实际执行 pytest，仅完成场景和参数校验。",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                stdout=json.dumps(
                    {
                        "scenario_ids": request.scenario_ids,
                        "selectors": selectors,
                        "pytest_args": request.pytest_args,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

        if shutil.which("pytest") is None and importlib.util.find_spec("pytest") is None:
            if self.runtime_logger is not None:
                self.runtime_logger.warning(
                    "pytest.execute.blocked",
                    "当前环境未检测到 pytest，执行被阻断。",
                    request_id=request.request_id,
                )
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.BLOCKED,
                total=len(request.scenario_ids),
                summary="当前环境未安装 pytest，无法执行自动化测试。",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                stderr="missing pytest",
            )

        command = [sys.executable, "-m", "pytest"]
        if selectors:
            command.extend(selectors)
        elif request.pytest_args:
            command.extend(request.pytest_args)
        else:
            command.append("tests")

        if self.runtime_logger is not None:
            # 执行命令是后续复盘失败现场的核心证据，需要在真正拉起 pytest 前先落日志。
            self.runtime_logger.info(
                "pytest.execute.start",
                "开始调用 pytest。",
                request_id=request.request_id,
                command=command,
                cwd=str(self.project_root),
                env_name=request.env_name,
            )
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "TEST_AGENT_ENV": request.env_name,
                    "TEST_AGENT_REQUEST_ID": request.request_id,
                },
            )
        except Exception:
            if self.runtime_logger is not None:
                self.runtime_logger.exception(
                    "pytest.execute.failed",
                    "调用 pytest 进程失败。",
                    request_id=request.request_id,
                    command=command,
                )
            raise
        stdout = completed.stdout
        stderr = completed.stderr
        passed, failed, skipped = self._extract_pytest_counts(stdout)
        total = max(passed + failed + skipped, len(request.scenario_ids))
        status = ExecutionStatus.SUCCESS if completed.returncode == 0 else ExecutionStatus.FAILED
        summary = (
            "pytest 执行完成。"
            if status is ExecutionStatus.SUCCESS
            else "pytest 执行失败，请查看失败用例与产物。"
        )
        failed_cases = self._extract_failed_cases(stdout)
        finished_at = datetime.now(UTC)
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "pytest.execute.complete",
                "pytest 执行完成。",
                request_id=request.request_id,
                returncode=completed.returncode,
                status=status.value,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                failed_case_count=len(failed_cases),
            )
        return ExecutionResult(
            request_id=request.request_id,
            status=status,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            summary=summary,
            started_at=started_at,
            finished_at=finished_at,
            stdout=stdout,
            stderr=stderr,
            failed_cases=failed_cases,
        )

    def _extract_pytest_counts(self, output: str) -> tuple[int, int, int]:
        passed = failed = skipped = 0
        for line in output.splitlines():
            lower_line = line.lower()
            if " passed" in lower_line or " failed" in lower_line or " skipped" in lower_line:
                segments = lower_line.replace(",", " ").split()
                for index, segment in enumerate(segments):
                    if segment == "passed" and index > 0:
                        passed = self._safe_int(segments[index - 1])
                    elif segment == "failed" and index > 0:
                        failed = self._safe_int(segments[index - 1])
                    elif segment == "skipped" and index > 0:
                        skipped = self._safe_int(segments[index - 1])
        return passed, failed, skipped

    def _extract_failed_cases(self, output: str) -> list[str]:
        cases: list[str] = []
        for line in output.splitlines():
            if "::" in line and ("FAILED" in line or "ERROR" in line):
                cases.append(line.strip())
        return cases

    @staticmethod
    def _safe_int(value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return 0
