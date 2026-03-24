from __future__ import annotations
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
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
    build_primary_button,
    show_error_dialog,
)


class RegressionPage(QWidget):
    def __init__(self, controller, runner: BackgroundRunner) -> None:
        super().__init__()
        self.controller = controller
        self.runner = runner
        self._build_ui()

    def _build_ui(self) -> None:
        scaffold = PageScaffold(
            "Bug 到回归场景映射",
            "输入自然语言 bug 描述，让智能体先从已保存场景中检索候选，再给出优先级更高的回归集合。",
            meta="回归路由",
        )
        layout = scaffold.content_layout
        page_splitter = QSplitter(Qt.Horizontal)
        page_splitter.setChildrenCollapsible(False)

        self.bug_input = QPlainTextEdit()
        self.bug_input.setPlaceholderText("输入 bug 描述、现象、模块和预期影响范围。")
        self.bug_input.setMinimumHeight(340)
        self.result_view = StructuredResultView(
            "推荐完成后，这里会展示命中的场景、优先级、推荐范围和原始 JSON。"
        )

        self.recommend_button = build_primary_button("推荐回归场景")
        self.recommend_button.clicked.connect(self._recommend)

        input_card = SectionCard("Bug 描述输入", "尽量写清楚模块、操作步骤、报错表现、预期结果和影响范围。")
        input_card.body_layout.addWidget(self.bug_input)
        input_card.body_layout.addWidget(self.recommend_button)

        strategy_card = SectionCard("输入建议", "高质量描述能显著提升回归命中率。")
        strategy_label = QLabel(
            "推荐格式：模块 + 操作步骤 + 实际现象 + 预期结果 + 是否影响新增功能。\n"
            "例如：审批配置页删除节点后，列表未刷新，预期应提示成功并更新表格。"
        )
        strategy_label.setWordWrap(True)
        strategy_card.body_layout.addWidget(strategy_label)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(input_card)
        left_layout.addWidget(strategy_card)
        left_layout.addStretch(1)

        result_card = SectionCard("推荐结果", "系统会结合场景索引和规则排序，给出优先执行的自动化场景。")
        result_card.body_layout.addWidget(self.result_view)

        page_splitter.addWidget(left_panel)
        page_splitter.addWidget(result_card)
        page_splitter.setStretchFactor(0, 4)
        page_splitter.setStretchFactor(1, 5)

        layout.addWidget(page_splitter)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scaffold)

    def _recommend(self) -> None:
        self.result_view.set_loading("正在检索并排序候选场景...", show_thinking_feedback=True)
        on_success, on_error = begin_async_button_feedback(
            self.recommend_button,
            busy_text="检索中...",
            on_success=self._show_result,
            on_error=self._show_error,
        )
        self.runner.submit(
            self.controller.recommend_regression,
            self.bug_input.toPlainText(),
            on_success=on_success,
            on_error=on_error,
        )

    def _show_result(self, suggestions) -> None:
        payload = [item.model_dump(mode="json") for item in suggestions]
        summary_html = (
            "<h3>推荐回归顺序</h3><ol>"
            + "".join(
                f"<li>{escape(item.title)} · {escape(item.module)} · 优先级 {escape(item.priority)} · {escape(item.rationale)}</li>"
                for item in suggestions
            )
            + "</ol>"
        )
        top_score = max((item.score for item in suggestions), default=0.0)
        self.result_view.set_result(
            status="回归推荐完成",
            metrics=[
                (str(len(suggestions)), "推荐场景"),
                (f"{top_score:.2f}", "最高匹配"),
            ],
            summary_html=summary_html,
            payload=payload,
        )

    def _show_error(self, message: str) -> None:
        self.result_view.set_result(
            status="回归推荐失败",
            metrics=[],
            summary_html=f"<h3>失败原因</h3><p>{escape(message)}</p>",
            payload=None,
        )
        show_error_dialog(self, title="回归推荐失败", message=message)
