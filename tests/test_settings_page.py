from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from local_test_agent.models import LLMCallLogEntry, LLMConnectionTestResult
from local_test_agent.ui.pages.settings_page import SettingsPage


@pytest.fixture()
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class ImmediateRunner:
    def submit(self, fn, *args, on_success, on_error, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - 测试桩仅用于模拟异常分支
            on_error(str(exc))
            return
        on_success(result)


def test_settings_page_saves_llm_and_yunxiao_separately(controller, qapp, monkeypatch):
    shown_messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "local_test_agent.ui.pages.settings_page.show_info_dialog",
        lambda *_args, title, message, **_kwargs: shown_messages.append((title, message)),
    )

    page = SettingsPage(controller, ImmediateRunner())
    page.llm_provider_model.setText("openai:gpt-4.1-mini")
    page.llm_base_url.setText("https://api.example.invalid/v1")
    page.llm_api_key.setText("llm-key")
    page.llm_enable_live.setChecked(True)
    page._save_llm_settings()

    page.yunxiao_api_base_url.setText("https://yunxiao.example.invalid")
    page.yunxiao_organization_id.setText("org-demo")
    page.yunxiao_project_id.setText("project-demo")
    page.yunxiao_access_token.setText("token-demo")
    page.yunxiao_create_defect_path.setText("/bugs")
    page._save_yunxiao_settings()

    payload = controller.load_settings()
    assert payload["llm_provider_model"] == "openai:gpt-4.1-mini"
    assert payload["llm_api_key"] == "llm-key"
    assert payload["yunxiao_project_id"] == "project-demo"
    assert shown_messages == [
        ("模型配置已保存", "模型配置已保存到本地。"),
        ("云效配置已保存", "云效配置已保存到本地。"),
    ]

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_settings_page_can_test_llm_configuration_without_saving(controller, qapp, monkeypatch):
    def fake_test_llm_settings(payload: dict[str, str]) -> LLMConnectionTestResult:
        assert payload["llm_provider_model"] == "openai:gpt-4.1"
        assert payload["llm_base_url"] == "https://probe.example.invalid/v1"
        assert payload["llm_api_key"] == "probe-key"
        assert payload["llm_enable_live"] == "true"
        return LLMConnectionTestResult(
            success=True,
            provider_model=payload["llm_provider_model"],
            base_url=payload["llm_base_url"],
            live_mode_enabled=True,
            message="模型调用成功，当前配置已生效。",
            response_excerpt="连接测试成功",
        )

    monkeypatch.setattr(controller, "test_llm_settings", fake_test_llm_settings)

    page = SettingsPage(controller, ImmediateRunner())
    page.llm_provider_model.setText("openai:gpt-4.1")
    page.llm_base_url.setText("https://probe.example.invalid/v1")
    page.llm_api_key.setText("probe-key")
    page.llm_enable_live.setChecked(True)

    page._test_llm_settings()

    assert page.llm_test_view.status_label is not None
    assert page.llm_test_view.status_label.text() == "模型配置测试通过"
    assert controller.settings.llm.provider_model != "openai:gpt-4.1"

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_settings_page_shows_failure_reason_for_llm_test(controller, qapp, monkeypatch):
    shown_errors: list[tuple[str, str]] = []

    def fake_test_llm_settings(_payload: dict[str, str]) -> LLMConnectionTestResult:
        return LLMConnectionTestResult(
            success=False,
            provider_model="openai:gpt-4.1",
            base_url="https://probe.example.invalid/v1",
            live_mode_enabled=True,
            message="模型调用失败：401 Unauthorized",
            response_excerpt="",
        )

    monkeypatch.setattr(controller, "test_llm_settings", fake_test_llm_settings)
    monkeypatch.setattr(
        "local_test_agent.ui.pages.settings_page.show_error_dialog",
        lambda *_args, title, message, **_kwargs: shown_errors.append((title, message)),
    )

    page = SettingsPage(controller, ImmediateRunner())
    page._test_llm_settings()

    assert shown_errors == [("模型配置测试未通过", "模型调用失败：401 Unauthorized")]
    assert page.llm_test_view.status_label is not None
    assert page.llm_test_view.status_label.text() == "模型配置测试未通过"
    assert page.llm_test_view.summary_browser is not None
    assert "失败原因" in page.llm_test_view.summary_browser.toPlainText()
    assert "401 Unauthorized" in page.llm_test_view.summary_browser.toPlainText()

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_settings_page_can_render_recent_llm_logs(controller, qapp, monkeypatch):
    monkeypatch.setattr(
        controller,
        "list_recent_llm_logs",
        lambda limit=50: [
            LLMCallLogEntry(
                operation="RequirementAnalysisAgent",
                success=False,
                used_fallback=True,
                live_mode_enabled=True,
                elapsed_ms=812,
                empty_output=True,
                fallback_reason="empty_structured_output",
                error_message="",
                prompt_preview="需求标题: 登录",
                response_preview="{}",
            )
        ],
    )

    page = SettingsPage(controller, ImmediateRunner())

    assert "RequirementAnalysisAgent" in page.llm_log_output.toPlainText()
    assert "empty_structured_output" in page.llm_log_output.toPlainText()
    assert "已回退：是" in page.llm_log_output.toPlainText()

    page.close()
    page.deleteLater()
    qapp.processEvents()
