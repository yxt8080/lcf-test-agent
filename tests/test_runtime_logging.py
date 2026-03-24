from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from local_test_agent.models import ExecutionRequest, ScenarioType
from local_test_agent.services.runtime_logger import RuntimeLogger
from local_test_agent.services.test_executor import TestExecutor as ExecutorService
from local_test_agent.store.database import LocalDatabase
from local_test_agent.store.runtime_log_store import RuntimeLogStore
from local_test_agent.ui.worker import BackgroundRunner


@pytest.fixture()
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _build_runtime_logger(tmp_path: Path) -> tuple[RuntimeLogger, RuntimeLogStore]:
    store = RuntimeLogStore(tmp_path / "runtime_events.log")
    return RuntimeLogger(store), store


def test_test_executor_records_dry_run_runtime_logs(tmp_path: Path):
    runtime_logger, store = _build_runtime_logger(tmp_path)
    database = LocalDatabase(tmp_path / "test_agent.db", runtime_logger=runtime_logger)
    executor = ExecutorService(tmp_path, database, runtime_logger=runtime_logger)

    request = ExecutionRequest(
        request_id="req-001",
        scenario_ids=["scene-a", "scene-b"],
        env_name="test",
        trigger_reason="manual",
        target_type=ScenarioType.UI,
        pytest_args=["tests/test_demo.py"],
        dry_run=True,
    )

    result = executor.run_tests(request)
    events = [entry.event for entry in store.read_recent(limit=10)]

    assert result.status.value == "success"
    assert "pytest.execute.prepare" in events
    assert "pytest.execute.dry_run" in events


def test_background_runner_records_failure_traceback(qapp, tmp_path: Path):
    runtime_logger, store = _build_runtime_logger(tmp_path)
    runner = BackgroundRunner(runtime_logger)
    failures: list[str] = []

    def explode() -> None:
        raise RuntimeError("boom")

    runner.submit(
        explode,
        on_success=lambda _result: None,
        on_error=lambda message: failures.append(message),
    )

    deadline = time.monotonic() + 2.0
    while not failures and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    logs = store.read_recent(limit=10)
    failed_entries = [entry for entry in logs if entry.event == "worker.task.failed"]

    assert failures == ["boom"]
    assert failed_entries
    assert "RuntimeError: boom" in failed_entries[0].traceback
