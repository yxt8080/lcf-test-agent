from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from local_test_agent.models import (
    BusinessCategory,
    BusinessSubcategory,
    ScenarioDetailLevel,
    ScenarioHandoffStatus,
)
from local_test_agent.ui.pages.automation_page import AutomationPage
from local_test_agent.ui.pages.execution_page import ExecutionPage
from local_test_agent.ui.pages.requirement_page import RequirementPage
from local_test_agent.ui.worker import BackgroundRunner


@pytest.fixture()
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _save_formal_requirement(controller, **kwargs):
    requirement = controller.create_requirement_input(**kwargs)
    draft = controller.start_requirement_analysis(requirement)
    assert draft.latest_analysis is not None
    controller.save_requirement_draft_handoff(
        scenario_statuses={
            item.scenario_id: ScenarioHandoffStatus.AUTOMATION.value
            for item in draft.latest_analysis.scenarios
        }
    )
    controller.confirm_requirement_draft()
    return requirement


def test_requirement_page_restores_active_draft_on_init(controller, qapp):
    requirement = controller.create_requirement_input(
        title="恢复草稿",
        markdown_content="# 恢复草稿\n## 主流程",
        image_paths=[],
        source="prd",
        notes="先保留为草稿",
    )
    controller.start_requirement_analysis(requirement)

    page = RequirementPage(controller, BackgroundRunner())

    assert page.current_draft is not None
    assert page.title_input.text() == "恢复草稿"
    assert "已恢复未保存草稿" in page.draft_status_label.text()

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_requirement_page_defaults_detail_level_to_standard(controller, qapp):
    page = RequirementPage(controller, BackgroundRunner())

    assert page.scenario_detail_level_input.currentData(Qt.UserRole) == ScenarioDetailLevel.STANDARD.value
    assert page.scenario_detail_level_input.currentText() == "标准测试"

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_delete_record_updates_management_list_immediately(controller, qapp, monkeypatch):
    requirement = _save_formal_requirement(
        controller,
        title="删除后刷新列表",
        markdown_content="# 删除后刷新列表\n## 主流程\n## 异常流",
        image_paths=[],
        source="prd",
        notes="",
    )

    page = RequirementPage(controller, BackgroundRunner())
    page.record_list.currentItemChanged.disconnect(page._handle_record_selection_changed)
    page.record_summaries = controller.list_requirement_records()
    page.current_record = controller.get_requirement_record(requirement.id)
    page.selected_record_id = requirement.id
    page._render_requirement_records(preferred_requirement_id=requirement.id)
    monkeypatch.setattr(page, "_refresh_requirement_records", lambda: None)

    assert page.record_list.count() == 1

    page._show_record_deleted(requirement.id)

    assert page.selected_record_id is None
    assert page.record_summaries == []
    assert page.record_list.count() == 0

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_refresh_requirement_records_populates_management_list(controller, qapp):
    _save_formal_requirement(
        controller,
        title="打开页面展示记录",
        markdown_content="# 打开页面展示记录\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )

    page = RequirementPage(controller, BackgroundRunner())
    page._refresh_requirement_records()

    assert len(page.record_summaries) == 1
    assert page.record_list.count() == 1

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_load_record_restores_business_category_fields(controller, qapp):
    controller.save_business_categories(
        [
            BusinessCategory(
                code="trade",
                name="交易中心",
                children=[BusinessSubcategory(code="refund", name="退款")],
            )
        ]
    )
    requirement = _save_formal_requirement(
        controller,
        title="载入业务分类",
        markdown_content="# 载入业务分类\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
        business_level1_code="trade",
        business_level1_name="交易中心",
        business_level2_code="refund",
        business_level2_name="退款",
        scenario_detail_level=ScenarioDetailLevel.DETAILED.value,
    )

    page = RequirementPage(controller, BackgroundRunner())
    page.current_record = controller.get_requirement_record(requirement.id)
    page._load_selected_record_into_analysis_tab()

    assert page.current_draft is not None
    assert page.workspace_mode_label.text() == "当前模式：编辑已保存记录"
    assert page.confirm_save_button.text() == "保存更新到当前记录"
    assert page.workspace_exit_button.text() == "退出编辑"
    assert page.business_level1_input.currentData(Qt.UserRole) == "trade"
    assert page.business_level1_input.currentText() == "交易中心"
    assert page.business_level2_input.currentData(Qt.UserRole) == "refund"
    assert page.business_level2_input.currentText() == "退款"
    assert page.scenario_detail_level_input.currentData(Qt.UserRole) == ScenarioDetailLevel.DETAILED.value
    assert page.scenario_detail_level_input.currentText() == "完整覆盖"

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_confirm_handoff_rejects_stale_workspace_without_active_draft(controller, qapp, monkeypatch):
    requirement = _save_formal_requirement(
        controller,
        title="过期草稿保护",
        markdown_content="# 过期草稿保护\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )

    page = RequirementPage(controller, BackgroundRunner())
    stale_draft = controller.create_requirement_draft_from_record(requirement.id)
    controller.discard_requirement_draft()
    page.current_draft = stale_draft

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "local_test_agent.ui.pages.requirement_page.show_warning_dialog",
        lambda *_args, title, message, **_kwargs: warnings.append((title, message)),
    )
    monkeypatch.setattr(
        page.runner,
        "submit",
        lambda *_args, **_kwargs: pytest.fail("活动草稿已不存在时不应继续提交后台动作"),
    )

    page._confirm_draft_handoff()

    assert warnings
    assert warnings[-1][0] == "无法确认场景处理方式"
    assert page.current_draft is None
    assert page.confirm_handoff_button.isEnabled() is False

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_confirm_handoff_success_disables_confirm_and_enables_save(controller, qapp):
    requirement = controller.create_requirement_input(
        title="确认按钮状态切换",
        markdown_content="# 确认按钮状态切换\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )
    draft = controller.start_requirement_analysis(requirement)
    assert draft.latest_analysis is not None

    page = RequirementPage(controller, BackgroundRunner())
    page._load_draft_into_workspace(draft, status="草稿已生成")

    assert page.confirm_handoff_button.isEnabled() is True
    assert page.confirm_save_button.isEnabled() is False

    saved_draft = controller.save_requirement_draft_handoff(
        scenario_statuses=page._scenario_statuses(),
    )
    page._show_draft_handoff_saved(saved_draft)

    assert page.confirm_handoff_button.isEnabled() is False
    assert page.confirm_save_button.isEnabled() is True
    assert "当前处理方式已确认" in page.selection_summary_label.text()

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_scenario_status_choice_buttons_use_compact_height(controller, qapp):
    requirement = controller.create_requirement_input(
        title="场景按钮高度",
        markdown_content="# 场景按钮高度\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )
    draft = controller.start_requirement_analysis(requirement)
    assert draft.latest_analysis is not None

    page = RequirementPage(controller, BackgroundRunner())
    page._load_draft_into_workspace(draft, status="草稿已生成")

    assert page.scenario_status_groups
    first_group = next(iter(page.scenario_status_groups.values()))
    for button in first_group.buttons():
        assert button.height() == 30

    priority_badges = [
        widget.text()
        for widget in page.scenario_table.findChildren(type(page.selection_summary_label))
        if widget.objectName() == "scenarioPriorityBadge"
    ]
    assert priority_badges
    assert priority_badges[0].startswith("P")

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_saved_record_keeps_priority_counts_in_selection_summary(controller, qapp, monkeypatch):
    requirement = controller.create_requirement_input(
        title="保存后优先级摘要",
        markdown_content="# 登录\n## 登录成功\n## 登录失败\n## 账号锁定",
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.DETAILED.value,
    )
    draft = controller.start_requirement_analysis(requirement)
    assert draft.latest_analysis is not None
    controller.save_requirement_draft_handoff(
        scenario_statuses={
            item.scenario_id: ScenarioHandoffStatus.AUTOMATION.value
            for item in draft.latest_analysis.scenarios
        }
    )

    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "local_test_agent.ui.pages.requirement_page.show_info_dialog",
        lambda *_args, **_kwargs: infos.append(("ok", "ok")),
    )

    page = RequirementPage(controller, BackgroundRunner())
    page._load_draft_into_workspace(controller.get_active_requirement_draft(), status="草稿已生成")
    page._show_draft_saved(controller.confirm_requirement_draft())

    assert infos
    assert "P0" in page.selection_summary_label.text()
    assert "P0 0 个，P1 0 个，P2 0 个，P3 0 个" not in page.selection_summary_label.text()

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_save_after_loading_record_keeps_edit_mode(controller, qapp, monkeypatch):
    requirement = _save_formal_requirement(
        controller,
        title="保存后继续编辑",
        markdown_content="# 保存后继续编辑\n## 主流程\n## 异常流",
        image_paths=[],
        source="prd",
        notes="",
    )

    page = RequirementPage(controller, BackgroundRunner())
    page.current_record = controller.get_requirement_record(requirement.id)
    page._load_selected_record_into_analysis_tab()
    assert page.current_draft is not None
    assert page.current_draft.source.name == "RECORD_EDIT"

    page.notes_input.setText("补充新的编辑说明")
    page.refinement_input.setPlainText("补充保存后的继续编辑说明")
    page._show_draft_refined(
        controller.refine_requirement_analysis(
            requirement=page._build_requirement_input(preserve_existing_id=True),
            user_input="补充保存后的继续编辑说明",
        )
    )
    page._show_draft_handoff_saved(
        controller.save_requirement_draft_handoff(
            scenario_statuses=page._scenario_statuses(),
        )
    )

    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "local_test_agent.ui.pages.requirement_page.show_info_dialog",
        lambda *_args, title, message, **_kwargs: infos.append((title, message)),
    )

    page._show_draft_saved(controller.confirm_requirement_draft())

    assert infos
    assert page.current_draft is not None
    assert page.current_draft.source.name == "RECORD_EDIT"
    assert page.workspace_mode_label.text() == "当前模式：编辑已保存记录"
    assert page.confirm_save_button.text() == "保存更新到当前记录"
    assert page.workspace_exit_button.text() == "退出编辑"
    assert "当前仍处于编辑模式" in page.draft_status_label.text()
    assert controller.get_active_requirement_draft() is not None

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_new_requirement_analysis_clears_current_edit_workspace(controller, qapp, monkeypatch):
    requirement = _save_formal_requirement(
        controller,
        title="切换到新需求",
        markdown_content="# 切换到新需求\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )

    page = RequirementPage(controller, BackgroundRunner())
    page.current_record = controller.get_requirement_record(requirement.id)
    page._load_selected_record_into_analysis_tab()
    assert page.current_draft is not None

    monkeypatch.setattr(
        "local_test_agent.ui.pages.requirement_page.ask_confirmation",
        lambda *_args, **_kwargs: True,
    )

    page._start_new_requirement_analysis()

    assert page.current_draft is None
    assert page.current_record is None
    assert page.workspace_mode_label.text() == "当前模式：新建分析"
    assert page.workspace_exit_button.text() == "清空工作区"
    assert page.title_input.text() == ""
    assert page.markdown_input.toPlainText() == ""

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_new_requirement_analysis_keeps_empty_workspace_without_confirmation(controller, qapp, monkeypatch):
    page = RequirementPage(controller, BackgroundRunner())
    asked: list[bool] = []
    monkeypatch.setattr(
        "local_test_agent.ui.pages.requirement_page.ask_confirmation",
        lambda *_args, **_kwargs: asked.append(True) or True,
    )

    page._start_new_requirement_analysis()

    assert asked == []
    assert page.workspace_mode_label.text() == "当前模式：新建分析"
    assert page.new_analysis_button.text() == "新建需求分析"
    assert page.workspace_exit_button.text() == "清空工作区"

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_combo_inputs_use_themed_popup_views(controller, qapp):
    runner = BackgroundRunner()
    requirement_page = RequirementPage(controller, runner)
    automation_page = AutomationPage(controller, runner)
    execution_page = ExecutionPage(controller, runner)

    assert requirement_page.business_level1_input.popupWidget().objectName() == "appSelectPopup"
    assert requirement_page.business_level2_input.popupWidget().objectName() == "appSelectPopup"
    assert automation_page.target_type.popupWidget().objectName() == "appSelectPopup"
    assert execution_page.target_type.popupWidget().objectName() == "appSelectPopup"

    requirement_page.close()
    automation_page.close()
    execution_page.close()
    requirement_page.deleteLater()
    automation_page.deleteLater()
    execution_page.deleteLater()
    qapp.processEvents()


def test_ui_pages_use_app_select_instead_of_qcombobox():
    page_dir = Path("src/local_test_agent/ui/pages")
    violating_files: list[str] = []

    for file_path in page_dir.glob("*.py"):
        module = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets":
                if any(alias.name == "QComboBox" for alias in node.names):
                    violating_files.append(str(file_path))
                    break
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "QComboBox":
                violating_files.append(str(file_path))
                break

    assert not violating_files, f"页面层请统一使用 AppSelect，不要直接使用 QComboBox：{violating_files}"


def test_requirement_page_switches_splitter_orientation_by_width(controller, qapp):
    page = RequirementPage(controller, BackgroundRunner())
    page.show()
    qapp.processEvents()

    page.resize(1600, 980)
    qapp.processEvents()
    assert page.page_splitter.orientation() == Qt.Horizontal
    assert page.record_splitter.orientation() == Qt.Horizontal

    page.resize(980, 980)
    qapp.processEvents()
    assert page.page_splitter.orientation() == Qt.Vertical
    assert page.record_splitter.orientation() == Qt.Vertical

    page.close()
    page.deleteLater()
    qapp.processEvents()
