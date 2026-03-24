from __future__ import annotations
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
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
    configure_combo_input,
    configure_form_layout,
    configure_line_input,
    show_error_dialog,
)


class ExecutionPage(QWidget):
    def __init__(self, controller, runner: BackgroundRunner) -> None:
        super().__init__()
        self.controller = controller
        self.runner = runner
        self._build_ui()

    def _build_ui(self) -> None:
        scaffold = PageScaffold(
            "自动化执行中心",
            "选择场景、环境与执行方式，后台触发 pytest 并自动归档日志和元数据。",
            meta="执行控制台",
        )
        layout = scaffold.content_layout
        page_splitter = QSplitter(Qt.Horizontal)
        page_splitter.setChildrenCollapsible(False)

        form = QFormLayout()

        self.scenario_ids_input = QLineEdit()
        self.scenario_ids_input.setPlaceholderText("例如：SCN-12345678-01,SCN-12345678-02")
        self.env_input = QLineEdit("test")
        self.trigger_input = QLineEdit("manual")
        self.target_type = AppSelect()
        self.target_type.addItems(["ui", "api", "mixed"])
        self.pytest_args_input = QLineEdit()
        self.pytest_args_input.setPlaceholderText("例如：tests/test_requirement_flow.py -k approval")
        self.dry_run_checkbox = QCheckBox("Dry-run（仅校验不执行）")
        configure_line_input(self.scenario_ids_input, min_width=520)
        configure_line_input(self.env_input, min_width=420)
        configure_line_input(self.trigger_input, min_width=420)
        configure_combo_input(self.target_type, min_width=420)
        configure_line_input(self.pytest_args_input, min_width=520)
        self.result_view = StructuredResultView(
            "执行完成后，这里会展示统计摘要、失败用例、产物和原始 JSON。"
        )

        configure_form_layout(form)
        form.addRow(build_form_label("场景 ID"), self.scenario_ids_input)
        form.addRow(build_form_label("环境"), self.env_input)
        form.addRow(build_form_label("触发原因"), self.trigger_input)
        form.addRow(build_form_label("目标类型"), self.target_type)
        form.addRow(build_form_label("pytest 参数"), self.pytest_args_input)
        form.addRow(build_form_label("执行模式"), self.dry_run_checkbox)

        self.run_button = build_primary_button("执行自动化")
        self.run_button.clicked.connect(self._run_tests)

        control_card = SectionCard("执行参数", "默认通过已保存的场景 ID 驱动执行，也支持直接传递 pytest 参数。")
        control_card.body_layout.addLayout(form)
        control_card.body_layout.addWidget(self.run_button)

        explain_card = SectionCard("执行说明", "长时间执行由后台线程处理，界面不会阻塞。")
        explain_label = QLabel(
            "1. 场景 ID 优先用于从本地索引中定位测试选择器。\n"
            "2. Dry-run 适合先校验参数和场景映射是否正确。\n"
            "3. 执行完成后，标准输出、错误输出和元数据会自动归档。"
        )
        explain_label.setWordWrap(True)
        explain_card.body_layout.addWidget(explain_label)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(control_card)
        left_layout.addWidget(explain_card)
        left_layout.addStretch(1)

        result_card = SectionCard("执行结果", "这里展示本次执行的结构化结果，便于后续报告生成和缺陷草稿整理。")
        result_card.body_layout.addWidget(self.result_view)

        page_splitter.addWidget(left_panel)
        page_splitter.addWidget(result_card)
        page_splitter.setStretchFactor(0, 4)
        page_splitter.setStretchFactor(1, 5)

        layout.addWidget(page_splitter)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scaffold)

    def _run_tests(self) -> None:
        request = self.controller.create_execution_request(
            scenario_ids=self.scenario_ids_input.text().split(","),
            env_name=self.env_input.text(),
            trigger_reason=self.trigger_input.text(),
            target_type=self.target_type.currentText(),
            pytest_args=[item for item in self.pytest_args_input.text().split(" ") if item],
            dry_run=self.dry_run_checkbox.isChecked(),
        )
        self.result_view.set_loading("正在执行自动化测试...")
        on_success, on_error = begin_async_button_feedback(
            self.run_button,
            busy_text="执行中...",
            on_success=self._show_result,
            on_error=self._show_error,
        )
        self.runner.submit(
            self.controller.run_tests,
            request,
            on_success=on_success,
            on_error=on_error,
        )

    def _show_result(self, result) -> None:
        summary_html = "\n".join(
            [
                f"<h3>执行摘要</h3><p>{escape(result.summary or '暂无摘要')}</p>",
                "<h3>失败用例</h3><ul>"
                + ("".join(f"<li>{escape(item)}</li>" for item in result.failed_cases) or "<li>无</li>")
                + "</ul>",
                "<h3>归档产物</h3><ul>"
                + ("".join(f"<li>{escape(item.kind)}：{escape(item.path)}</li>" for item in result.artifacts) or "<li>无</li>")
                + "</ul>",
            ]
        )
        self.result_view.set_result(
            status=f"执行完成 | {result.status.value}",
            metrics=[
                (str(result.total), "总用例"),
                (str(result.passed), "通过"),
                (str(result.failed), "失败"),
                (str(result.skipped), "跳过"),
            ],
            summary_html=summary_html,
            payload=result.model_dump(mode="json"),
        )

    def _show_error(self, message: str) -> None:
        self.result_view.set_result(
            status="执行失败",
            metrics=[],
            summary_html=f"<h3>失败原因</h3><p>{escape(message)}</p>",
            payload=None,
        )
        show_error_dialog(self, title="执行失败", message=message)
