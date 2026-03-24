from __future__ import annotations
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from local_test_agent.ui.worker import BackgroundRunner
from local_test_agent.ui.widgets import (
    AppSelect,
    PageScaffold,
    SectionCard,
    StructuredResultView,
    begin_async_button_feedback,
    build_form_label,
    build_primary_button,
    build_secondary_button,
    configure_combo_input,
    configure_expanding_container,
    configure_form_layout,
    configure_line_input,
    configure_text_input,
    show_error_dialog,
)


class AutomationPage(QWidget):
    def __init__(self, controller, runner: BackgroundRunner) -> None:
        super().__init__()
        self.controller = controller
        self.runner = runner
        self._build_ui()

    def _build_ui(self) -> None:
        scaffold = PageScaffold(
            "自动化任务包生成",
            "优先读取需求分析页中标记为“纳入自动化”的测试场景，再结合页面说明和 OpenAPI 文档整理开发上下文。",
            meta="编码协作台",
        )
        layout = scaffold.content_layout
        page_splitter = QSplitter(Qt.Horizontal)
        page_splitter.setChildrenCollapsible(False)

        self.requirement_title_input = QLineEdit()
        self.requirement_title_input.setPlaceholderText("输入已经做过需求分析的标题")
        self.openapi_input = QLineEdit()
        self.openapi_input.setPlaceholderText("选择 Swagger/OpenAPI JSON 或 YAML")
        self.page_summary_input = QPlainTextEdit()
        self.page_summary_input.setPlaceholderText("描述页面字段、交互、弹窗、表格、状态提示等可见信息。")
        self.target_type = AppSelect()
        self.target_type.addItems(["ui", "api", "mixed"])
        configure_line_input(self.requirement_title_input, min_width=460)
        configure_line_input(self.openapi_input, min_width=460)
        configure_combo_input(self.target_type, min_width=460)
        configure_text_input(self.page_summary_input, min_width=620, min_height=340)
        self.result_view = StructuredResultView(
            "任务包生成后，这里会展示目标类型、场景摘要、验收要求和原始 JSON。"
        )

        self.browse_button = build_secondary_button("选择 OpenAPI 文档")
        self.browse_button.clicked.connect(self._pick_openapi)
        self.plan_button = build_primary_button("生成自动化任务包")
        self.plan_button.clicked.connect(self._plan_automation)

        openapi_row = QHBoxLayout()
        openapi_row.setContentsMargins(0, 0, 0, 0)
        openapi_row.setSpacing(10)
        openapi_row.addWidget(self.openapi_input)
        openapi_row.addWidget(self.browse_button)
        openapi_widget = QWidget()
        openapi_widget.setLayout(openapi_row)
        configure_expanding_container(openapi_widget, min_width=620)

        form_card = SectionCard("输入区", "页面说明越具体，生成的 UI/API 自动化任务包越稳定。")
        form = QFormLayout()
        configure_form_layout(form)
        form.addRow(build_form_label("需求标题"), self.requirement_title_input)
        form.addRow(build_form_label("目标类型"), self.target_type)
        form.addRow(build_form_label("OpenAPI"), openapi_widget)
        form.addRow(build_form_label("页面说明"), self.page_summary_input)
        form_card.body_layout.addLayout(form)
        form_card.body_layout.addWidget(self.plan_button)

        tips_card = SectionCard("提示", "推荐先在需求分析页确认测试场景处理方式，本页会优先读取“纳入自动化”的那批测试场景。")
        tips_label = QLabel(
            "1. UI 场景请重点说明页面入口、关键字段、按钮文案和表格反馈。\n"
            "2. API 场景请优先提供完整的 Swagger/OpenAPI 文档。\n"
            "3. 若未确认测试场景处理方式，系统会回退使用整份需求分析结果。"
        )
        tips_label.setWordWrap(True)
        tips_card.body_layout.addWidget(tips_label)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(form_card)
        left_layout.addWidget(tips_card)
        left_layout.addStretch(1)

        result_card = SectionCard("自动化任务包", "右侧输出可直接复制给 Codex / Claude Code，也可作为后续自动化开发说明。")
        result_card.body_layout.addWidget(self.result_view)

        page_splitter.addWidget(left_panel)
        page_splitter.addWidget(result_card)
        page_splitter.setStretchFactor(0, 4)
        page_splitter.setStretchFactor(1, 5)

        layout.addWidget(page_splitter)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scaffold)

    def _pick_openapi(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 OpenAPI 文档",
            "",
            "OpenAPI (*.json *.yaml *.yml)",
        )
        if file_path:
            self.openapi_input.setText(file_path)

    def _plan_automation(self) -> None:
        self.result_view.set_loading("正在生成自动化任务包...", show_thinking_feedback=True)
        on_success, on_error = begin_async_button_feedback(
            self.plan_button,
            busy_text="任务包生成中...",
            on_success=self._show_result,
            on_error=self._show_error,
            disable_widgets=[self.browse_button],
        )
        self.runner.submit(
            self.controller.plan_automation,
            requirement_title=self.requirement_title_input.text(),
            page_summary=self.page_summary_input.toPlainText(),
            openapi_path=self.openapi_input.text(),
            target_type=self.target_type.currentText(),
            on_success=on_success,
            on_error=on_error,
        )

    def _show_result(self, result) -> None:
        summary_html = "\n".join(
            [
                f"<h3>上下文摘要</h3><p>{escape(result.context_summary)}</p>",
                "<h3>场景覆盖</h3><ul>"
                + "".join(
                    f"<li>{escape(item.scenario_id)} · {escape(item.title)} · {escape(item.module)}</li>"
                    for item in result.scenarios[:8]
                )
                + "</ul>",
                "<h3>验收要求</h3><ul>"
                + "".join(f"<li>{escape(item)}</li>" for item in result.acceptance_checks)
                + "</ul>",
            ]
        )
        self.result_view.set_result(
            status="自动化任务包已生成",
            metrics=[
                (result.target_type.value.upper(), "目标类型"),
                (str(len(result.scenarios)), "场景数"),
                (str(len(result.acceptance_checks)), "验收项"),
                (str(len(result.file_naming_rules)), "命名规则"),
            ],
            summary_html=summary_html,
            payload=result.model_dump(mode="json"),
        )

    def _show_error(self, message: str) -> None:
        self.result_view.set_result(
            status="自动化设计失败",
            metrics=[],
            summary_html=f"<h3>失败原因</h3><p>{escape(message)}</p>",
            payload=None,
        )
        show_error_dialog(self, title="自动化设计失败", message=message)
