from __future__ import annotations

from pathlib import Path

import pytest

from local_test_agent.bootstrap import build_controller


@pytest.fixture()
def controller(tmp_path: Path):
    return build_controller(tmp_path)

