from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from local_test_agent.ui.widgets import (
    ButtonBusyState,
    StructuredResultView,
    begin_async_button_feedback,
    build_primary_button,
    build_secondary_button,
)


@pytest.fixture()
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def test_button_busy_state_restores_button_and_preserves_disabled_widget(qapp):
    primary_button = build_primary_button("执行自动化")
    secondary_button = build_secondary_button("刷新记录")
    secondary_button.setEnabled(False)

    busy_state = ButtonBusyState(
        primary_button,
        busy_text="执行中...",
        disable_widgets=[secondary_button],
    )

    busy_state.start()

    assert primary_button.text() == "执行中..."
    assert primary_button.isEnabled() is False
    assert primary_button.property("interactionState") == "busy"
    assert secondary_button.isEnabled() is False

    busy_state.finish()

    assert primary_button.text() == "执行自动化"
    assert primary_button.isEnabled() is True
    assert primary_button.property("interactionState") == "idle"
    assert secondary_button.isEnabled() is False

    primary_button.deleteLater()
    secondary_button.deleteLater()
    qapp.processEvents()


def test_async_button_feedback_restores_state_before_callback(qapp):
    action_button = build_primary_button("生成任务包")
    callback_snapshot: list[tuple[str, str, bool, str]] = []

    on_success, _on_error = begin_async_button_feedback(
        action_button,
        busy_text="生成中...",
        on_success=lambda result: callback_snapshot.append(
            (
                result,
                action_button.text(),
                action_button.isEnabled(),
                action_button.property("interactionState"),
            )
        ),
        on_error=lambda _message: None,
    )

    assert action_button.text() == "生成中..."
    assert action_button.isEnabled() is False

    on_success("ok")

    assert callback_snapshot == [("ok", "生成任务包", True, "idle")]

    action_button.deleteLater()
    qapp.processEvents()


def test_structured_result_view_shows_thinking_feedback_and_elapsed_time(qapp, monkeypatch):
    timestamps = iter([10.0, 11.2, 12.5])
    monkeypatch.setattr("local_test_agent.ui.widgets.monotonic", lambda: next(timestamps))

    result_view = StructuredResultView("等待结果")
    result_view.set_loading("正在生成需求分析草稿，请稍候...", show_thinking_feedback=True)

    assert result_view.status_feedback_wrap is not None
    assert result_view.status_indicator_label is not None
    assert result_view.status_meta_label is not None
    assert result_view.status_feedback_wrap.isHidden() is False
    assert result_view.status_indicator_label.isHidden() is False
    assert result_view.status_indicator_label.text() == "● ○ ○"
    assert result_view.status_meta_label.isHidden() is False
    assert result_view.status_meta_label.text() == "思考中  已耗时 1.2s"

    result_view.set_result(
        status="需求分析完成",
        metrics=[],
        summary_html="<p>ok</p>",
        payload={"ok": True},
    )

    assert result_view.status_indicator_label.text() == ""
    assert result_view.status_indicator_label.isHidden() is True
    assert result_view.status_meta_label.text() == "本次大模型调用耗时 2.5s"
    assert result_view.status_meta_label.isHidden() is False

    result_view.deleteLater()
    qapp.processEvents()


def test_structured_result_view_keeps_non_llm_loading_without_thinking_feedback(qapp):
    result_view = StructuredResultView("等待结果")

    result_view.set_loading("正在加载需求记录，请稍候...")

    assert result_view.status_feedback_wrap is not None
    assert result_view.status_indicator_label is not None
    assert result_view.status_meta_label is not None
    assert result_view.status_feedback_wrap.isHidden() is True
    assert result_view.status_indicator_label.isHidden() is True
    assert result_view.status_indicator_label.text() == ""
    assert result_view.status_meta_label.isHidden() is True
    assert result_view.status_meta_label.text() == ""

    result_view.deleteLater()
    qapp.processEvents()
