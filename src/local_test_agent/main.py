from __future__ import annotations

import sys
from pathlib import Path

from local_test_agent.bootstrap import build_controller


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - 依赖未安装时仅控制台提示
        raise SystemExit(
            "当前环境未安装 PySide6，请先执行 `.venv/bin/pip install -e .[dev]`。"
        ) from exc

    from local_test_agent.ui.main_window import MainWindow

    project_root = Path(__file__).resolve().parents[2]
    controller = build_controller(project_root)

    app = QApplication(sys.argv)
    window = MainWindow(controller)
    window.show()
    sys.exit(app.exec())
