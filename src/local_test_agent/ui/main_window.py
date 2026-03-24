from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from local_test_agent.ui.pages.automation_page import AutomationPage
from local_test_agent.ui.pages.business_category_page import BusinessCategoryPage
from local_test_agent.ui.pages.execution_page import ExecutionPage
from local_test_agent.ui.pages.regression_page import RegressionPage
from local_test_agent.ui.pages.reports_page import ReportsPage
from local_test_agent.ui.pages.requirement_page import RequirementPage
from local_test_agent.ui.pages.settings_page import SettingsPage
from local_test_agent.ui.theme import build_font, build_palette, build_stylesheet
from local_test_agent.ui.worker import BackgroundRunner


class MainWindow(QMainWindow):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.runner = BackgroundRunner(controller.runtime_logger)
        self.page_stack = QStackedWidget()
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("本地测试智能体工作台")
        self.resize(1440, 920)
        self.setMinimumSize(1260, 820)
        self.setFont(build_font())
        self.setPalette(build_palette())
        self.setStyleSheet(build_stylesheet())

        main_shell = QFrame()
        main_shell.setObjectName("mainShell")
        shell_layout = QHBoxLayout(main_shell)
        shell_layout.setContentsMargins(24, 24, 24, 24)
        shell_layout.setSpacing(20)

        shell_layout.addWidget(self._build_side_rail(), 0)
        shell_layout.addWidget(self._build_workspace(), 1)

        self.setCentralWidget(main_shell)
        self.statusBar().showMessage("当前页：需求分析 | 配置、执行与报告均在本地完成")

    def _build_side_rail(self) -> QWidget:
        runtime = self.controller.export_runtime_state()
        counts = runtime.get("database", {}).get("counts", {})
        llm_mode = "实时模型" if self.controller.settings.llm.enable_live_llm else "规则回退"

        rail = QFrame()
        rail.setObjectName("sideRail")
        rail.setFixedWidth(288)

        layout = QVBoxLayout(rail)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        eyebrow = QLabel("LOCAL TEST WORKBENCH")
        eyebrow.setObjectName("railEyebrow")
        title = QLabel("测试智能体")
        title.setObjectName("railTitle")
        subtitle = QLabel("围绕需求分析、自动化协作、回归推荐与执行反馈的单机工作台。")
        subtitle.setObjectName("railSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        section = QLabel("Navigation")
        section.setObjectName("railSection")
        layout.addWidget(section)

        # 侧边栏负责工作流一级切换，页面内部继续处理具体业务步骤。
        for index, title in enumerate(
            ["需求分析", "自动化设计", "回归推荐", "执行中心", "报告与缺陷", "业务分类", "设置"]
        ):
            button = self._build_nav_button(title, index)
            layout.addWidget(button)

        stats_card = QFrame()
        stats_card.setObjectName("railStats")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(18, 18, 18, 18)
        stats_layout.setSpacing(12)
        stats_layout.addWidget(self._build_stat_block(str(counts.get("requirements", 0)), "需求记录"))
        stats_layout.addWidget(self._build_stat_block(str(counts.get("scenarios", 0)), "场景索引"))
        stats_layout.addWidget(self._build_stat_block(str(counts.get("executions", 0)), f"执行记录 | {llm_mode}"))

        layout.addWidget(stats_card)
        layout.addStretch(1)

        footer = QLabel("本地优先、人工确认优先。界面负责操作流畅性，智能体负责结构化推理。")
        footer.setObjectName("railFooter")
        footer.setWordWrap(True)
        layout.addWidget(footer)
        return rail

    def _build_workspace(self) -> QWidget:
        workspace = QFrame()
        workspace.setObjectName("workspaceCanvas")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self.page_stack.setObjectName("workspaceStack")

        self.page_stack.addWidget(RequirementPage(self.controller, self.runner))
        self.page_stack.addWidget(AutomationPage(self.controller, self.runner))
        self.page_stack.addWidget(RegressionPage(self.controller, self.runner))
        self.page_stack.addWidget(ExecutionPage(self.controller, self.runner))
        self.page_stack.addWidget(ReportsPage(self.controller, self.runner))
        self.page_stack.addWidget(BusinessCategoryPage(self.controller))
        self.page_stack.addWidget(SettingsPage(self.controller, self.runner))

        layout.addWidget(self.page_stack)
        self._activate_page(0, "需求分析")
        return workspace

    def _build_nav_button(self, title: str, index: int) -> QPushButton:
        button = QPushButton(title)
        button.setProperty("role", "nav")
        button.setCheckable(True)
        button.clicked.connect(lambda checked=False, idx=index, name=title: self._activate_page(idx, name))
        self.nav_group.addButton(button, index)
        if index == 0:
            button.setChecked(True)
        button.style().unpolish(button)
        button.style().polish(button)
        return button

    def _build_stat_block(self, value: str, label: str) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setObjectName("railStatValue")
        text_label = QLabel(label)
        text_label.setObjectName("railStatLabel")
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)
        return block

    def _activate_page(self, index: int, title: str) -> None:
        self.page_stack.setCurrentIndex(index)
        self.statusBar().showMessage(f"当前页：{title} | 配置、执行与报告均在本地完成")
