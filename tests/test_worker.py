from __future__ import annotations

import os
import time

import pytest
from PySide6.QtWidgets import QApplication

from local_test_agent.ui.worker import BackgroundRunner


@pytest.fixture()
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def test_background_runner_invokes_success_callback(qapp):
    runner = BackgroundRunner()
    received: list[int] = []
    failures: list[str] = []

    runner.submit(
        lambda: 7,
        on_success=lambda result: received.append(result),
        on_error=lambda message: failures.append(message),
    )

    deadline = time.monotonic() + 2.0
    while not received and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert received == [7]
    assert failures == []
