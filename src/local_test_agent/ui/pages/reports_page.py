from __future__ import annotations
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from local_test_agent.ui.worker import BackgroundRunner
from local_test_agent.ui.widgets import (
    PageScaffold,
    SectionCard,
    StructuredResultView,
    begin_async_button_feedback,
    build_form_label,
    build_primary_button,
    build_secondary_button,
    configure_form_layout,
    configure_line_input,
    show_error_dialog,
)


class ReportsPage(QWidget):
    def __init__(self, controller, runner: BackgroundRunner) -> None:
        super().__init__()
        self.controller = controller
        self.runner = runner
        self.current_draft = None
        self._build_ui()

    def _build_ui(self) -> None:
        scaffold = PageScaffold(
            "报告生成与缺陷草稿",
            "基于执行记录产出报告、缺陷草稿和云效提单动作。提交前依然保留人工确认，降低误提单风险。",
            meta="反馈中心",
        )
        layout = scaffold.content_layout
        page_splitter = QSplitter(Qt.Horizontal)
        page_splitter.setChildrenCollapsible(False)
        form = QFormLayout()

        self.request_id_input = QLineEdit()
        self.request_id_input.setPlaceholderText("可空，默认使用最近一次执行结果")
        self.requirement_id_input = QLineEdit()
        self.requirement_id_input.setPlaceholderText("可选，用于关联需求")
        self.environment_input = QLineEdit("test")
        configure_line_input(self.request_id_input, min_width=500)
        configure_line_input(self.requirement_id_input, min_width=500)
        configure_line_input(self.environment_input, min_width=420)
        self.result_view = StructuredResultView(
            "生成报告、缺陷草稿或云效提交结果后，这里会展示摘要和原始 JSON。"
        )

        configure_form_layout(form)
        form.addRow(build_form_label("执行请求 ID"), self.request_id_input)
        form.addRow(build_form_label("需求 ID"), self.requirement_id_input)
        form.addRow(build_form_label("环境"), self.environment_input)

        self.report_button = build_secondary_button("生成测试报告")
        self.report_button.clicked.connect(self._generate_report)
        self.defect_button = build_primary_button("生成缺陷草稿")
        self.defect_button.clicked.connect(self._build_defect)
        self.submit_button = build_secondary_button("提交到云效")
        self.submit_button.clicked.connect(self._submit_defect)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)
        button_row.addWidget(self.report_button)
        button_row.addWidget(self.defect_button)
        button_row.addWidget(self.submit_button)
        button_row.addStretch(1)

        control_card = SectionCard("操作区", "建议先生成报告，再生成缺陷草稿，最后人工确认后提交到云效。")
        control_card.body_layout.addLayout(form)
        control_card.body_layout.addLayout(button_row)

        note_card = SectionCard("提单约束", "当前默认保留人工确认，不直接全自动远程提单。")
        note_label = QLabel(
            "1. 若未配置云效接口，系统会先导出本地草稿。\n"
            "2. 缺陷草稿会尽量汇总失败摘要、复现步骤、期望与实际结果。\n"
            "3. 报告与缺陷预览文件会一起保存到 reports 目录。"
        )
        note_label.setWordWrap(True)
        note_card.body_layout.addWidget(note_label)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(control_card)
        left_layout.addWidget(note_card)
        left_layout.addStretch(1)

        result_card = SectionCard("输出区", "包含报告路径、缺陷草稿 JSON 和提单返回结果。")
        result_card.body_layout.addWidget(self.result_view)

        page_splitter.addWidget(left_panel)
        page_splitter.addWidget(result_card)
        page_splitter.setStretchFactor(0, 4)
        page_splitter.setStretchFactor(1, 5)

        layout.addWidget(page_splitter)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scaffold)

    def _generate_report(self) -> None:
        self.result_view.set_loading("正在生成测试报告...")
        on_success, on_error = begin_async_button_feedback(
            self.report_button,
            busy_text="报告生成中...",
            on_success=self._show_result,
            on_error=self._show_error,
            disable_widgets=[self.defect_button, self.submit_button],
        )
        self.runner.submit(
            self.controller.generate_execution_report,
            self.request_id_input.text().strip() or None,
            on_success=on_success,
            on_error=on_error,
        )

    def _build_defect(self) -> None:
        self.result_view.set_loading("正在生成缺陷草稿...", show_thinking_feedback=True)
        on_success, on_error = begin_async_button_feedback(
            self.defect_button,
            busy_text="草稿生成中...",
            on_success=self._store_draft,
            on_error=self._show_error,
            disable_widgets=[self.report_button, self.submit_button],
        )
        self.runner.submit(
            self.controller.build_defect_draft,
            self.request_id_input.text().strip() or None,
            requirement_id=self.requirement_id_input.text().strip() or None,
            environment=self.environment_input.text().strip() or "test",
            on_success=on_success,
            on_error=on_error,
        )

    def _submit_defect(self) -> None:
        if self.current_draft is None:
            self._show_error("请先生成缺陷草稿并确认内容。")
            return
        on_success, on_error = begin_async_button_feedback(
            self.submit_button,
            busy_text="提交中...",
            on_success=self._show_submit_result,
            on_error=self._show_error,
            disable_widgets=[self.report_button, self.defect_button],
        )
        self.runner.submit(
            self.controller.submit_defect,
            self.current_draft,
            on_success=on_success,
            on_error=on_error,
        )

    def _show_result(self, payload) -> None:
        summary_html = (
            "<h3>报告产物</h3><ul>"
            + "".join(f"<li>{escape(key)}：{escape(value)}</li>" for key, value in payload.items())
            + "</ul>"
        )
        self.result_view.set_result(
            status="测试报告已生成",
            metrics=[(str(len(payload)), "输出文件")],
            summary_html=summary_html,
            payload=payload,
        )

    def _store_draft(self, draft) -> None:
        self.current_draft = draft
        summary_html = "\n".join(
            [
                f"<h3>缺陷标题</h3><p>{escape(draft.title)}</p>",
                f"<h3>描述</h3><p>{escape(draft.description)}</p>",
                "<h3>复现步骤</h3><ol>"
                + "".join(f"<li>{escape(item)}</li>" for item in draft.repro_steps)
                + "</ol>",
            ]
        )
        self.result_view.set_result(
            status="缺陷草稿已生成",
            metrics=[
                (str(len(draft.repro_steps)), "复现步骤"),
                (str(len(draft.attachments)), "附件"),
            ],
            summary_html=summary_html,
            payload=draft.model_dump(mode="json"),
        )

    def _show_submit_result(self, defect_id: str) -> None:
        self.result_view.set_result(
            status="云效提交完成",
            metrics=[("1", "提交结果")],
            summary_html=f"<h3>缺陷提交结果</h3><p>已返回标识：<strong>{escape(defect_id)}</strong></p>",
            payload={"defect_id": defect_id},
        )

    def _show_error(self, message: str) -> None:
        self.result_view.set_result(
            status="报告/缺陷操作失败",
            metrics=[],
            summary_html=f"<h3>失败原因</h3><p>{escape(message)}</p>",
            payload=None,
        )
        show_error_dialog(self, title="报告/缺陷操作失败", message=message)
