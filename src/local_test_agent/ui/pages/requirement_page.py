from __future__ import annotations

from html import escape

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from local_test_agent.models import (
    BusinessCategory,
    RequirementAnalysisDraft,
    RequirementDraftSource,
    ScenarioDetailLevel,
    ScenarioHandoffStatus,
    ScenarioKind,
    ScenarioPriority,
)
from local_test_agent.ui.worker import BackgroundRunner
from local_test_agent.ui.widgets import (
    AppSelect,
    CollapsibleSection,
    PageScaffold,
    ScenarioHandoffList,
    SectionCard,
    StructuredResultView,
    ask_confirmation,
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
    show_info_dialog,
    show_warning_dialog,
)


class RequirementPage(QWidget):
    ANALYSIS_VERTICAL_BREAKPOINT = 1320
    RECORDS_VERTICAL_BREAKPOINT = 1180
    STATUS_LABELS = {
        ScenarioHandoffStatus.AUTOMATION: "纳入自动化",
        ScenarioHandoffStatus.REGRESSION_ONLY: "仅做回归",
        ScenarioHandoffStatus.DEFERRED: "暂不处理",
    }
    SCENARIO_KIND_LABELS = {
        ScenarioKind.MAIN_FLOW: "主流程",
        ScenarioKind.KEY_EXCEPTION: "关键异常",
        ScenarioKind.BOUNDARY: "边界校验",
        ScenarioKind.PERMISSION: "权限",
        ScenarioKind.STATE_TRANSITION: "状态流转",
    }

    def __init__(self, controller, runner: BackgroundRunner) -> None:
        super().__init__()
        self.controller = controller
        self.runner = runner
        self.current_draft: RequirementAnalysisDraft | None = None
        self.current_record = None
        self.record_summaries = []
        self.selected_record_id: str | None = None
        self.workspace_requirement_id: str | None = None
        self.scenario_status_groups: dict[str, QButtonGroup] = {}
        self.displayed_scenarios: list = []
        self.business_categories: list[BusinessCategory] = []
        self._restoring_scenario_statuses = False
        self._build_ui()
        self._load_business_categories()
        self._restore_active_draft_from_store()

    def _build_ui(self) -> None:
        scaffold = PageScaffold(
            "需求拆解与测试路径设计",
            "先在草稿区做初次分析和多轮补充，确认无误后再保存正式需求记录。",
            meta="分析工作台",
        )
        layout = scaffold.content_layout
        self.page_splitter = QSplitter(Qt.Horizontal)
        self.page_splitter.setChildrenCollapsible(False)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例如：订单审批流新增驳回原因")
        self.source_input = QLineEdit("需求文档")
        self.source_input.setPlaceholderText("例如：PRD / Jira / 口头需求")
        self.business_level1_input = AppSelect()
        self.business_level2_input = AppSelect()
        self.scenario_detail_level_input = AppSelect()
        self.images_input = QLineEdit()
        self.images_input.setPlaceholderText("可选择多张截图，系统会自动拼接路径")
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("补充背景、风险或测试重点")
        self.markdown_input = QPlainTextEdit()
        self.markdown_input.setPlaceholderText("粘贴 Markdown 需求正文，建议包含功能点、交互说明、异常规则。")
        configure_line_input(self.title_input, min_width=280)
        configure_line_input(self.source_input, min_width=280)
        configure_combo_input(self.business_level1_input, min_width=280)
        configure_combo_input(self.business_level2_input, min_width=280)
        configure_combo_input(self.scenario_detail_level_input, min_width=280)
        configure_line_input(self.images_input, min_width=280)
        configure_line_input(self.notes_input, min_width=280)
        configure_text_input(self.markdown_input, min_width=360, min_height=320)
        self.business_level1_input.currentIndexChanged.connect(self._handle_business_level1_changed)
        self._populate_detail_level_options()

        self.initial_analyze_button = build_primary_button("初次分析")
        self.initial_analyze_button.clicked.connect(self._analyze_requirement)
        self.new_analysis_button = build_secondary_button("新建需求分析")
        self.new_analysis_button.clicked.connect(self._start_new_requirement_analysis)
        self.workspace_exit_button = build_secondary_button("退出编辑")
        self.workspace_exit_button.clicked.connect(self._discard_draft)
        self.workspace_action_hint_label = QLabel("需要切换到全新需求时，直接点“新建需求分析”。")
        self.workspace_action_hint_label.setWordWrap(True)

        browse_button = build_secondary_button("选择截图")
        browse_button.clicked.connect(self._pick_images)

        image_row = QHBoxLayout()
        image_row.setContentsMargins(0, 0, 0, 0)
        image_row.setSpacing(10)
        image_row.addWidget(self.images_input)
        image_row.addWidget(browse_button)
        image_widget = QWidget()
        image_widget.setLayout(image_row)
        configure_expanding_container(image_widget, min_width=360)

        form_card = SectionCard("输入区", "在这里整理当前需求文本。开始分析后会生成一个本地草稿工作区。")
        form = QFormLayout()
        configure_form_layout(form)
        form.addRow(build_form_label("需求标题"), self.title_input)
        form.addRow(build_form_label("需求来源"), self.source_input)
        form.addRow(build_form_label("一级业务"), self.business_level1_input)
        form.addRow(build_form_label("二级业务"), self.business_level2_input)
        form.addRow(build_form_label("截图素材"), image_widget)
        form.addRow(build_form_label("补充说明"), self.notes_input)
        form.addRow(build_form_label("场景覆盖范围"), self.scenario_detail_level_input)
        form.addRow(build_form_label("Markdown"), self.markdown_input)
        form_card.body_layout.addLayout(form)
        form_card.body_layout.addWidget(self.initial_analyze_button)

        guide_card = SectionCard("测试设计建议", "先收敛需求事实，再用多轮补充逐步完善，最后统一确认保存。")
        guide_label = QLabel(
            "1. 初次分析只生成草稿，不会直接进入需求记录。\n"
            "2. 每轮补充后系统都会基于完整上下文重算结果。\n"
            "3. 只要重新分析过一次，就需要重新确认场景处理方式。"
        )
        guide_label.setWordWrap(True)
        self.guide_section = CollapsibleSection(
            "测试设计建议",
            "需要时再展开查看",
            expanded=False,
        )
        self.guide_section.body_layout.addWidget(guide_label)

        self.draft_status_label = QLabel("当前没有活动草稿。")
        self.draft_status_label.setWordWrap(True)
        self.draft_status_label.setObjectName("workspaceStatusHighlight")
        self.workspace_mode_label = QLabel("当前模式：新建分析")
        self.workspace_mode_label.setWordWrap(True)
        self.workspace_mode_label.setObjectName("workspaceStatusTitle")
        self.draft_change_label = QLabel("尚未开始需求分析。")
        self.draft_change_label.setWordWrap(True)
        self.draft_change_label.setObjectName("workspaceStatusMeta")
        self.workspace_action_hint_label.setObjectName("workspaceStatusMeta")
        self.confirm_save_button = build_primary_button("确认保存正式记录")
        self.confirm_save_button.clicked.connect(self._confirm_save_draft)

        workspace_toolbar_card = SectionCard(
            "当前工作区",
            "主流程信息固定展示，辅助说明按需展开，减少首屏干扰。",
        )
        workspace_toolbar_row = QHBoxLayout()
        workspace_toolbar_row.setContentsMargins(0, 0, 0, 0)
        workspace_toolbar_row.setSpacing(16)

        workspace_summary_panel = QWidget()
        workspace_summary_panel.setObjectName("workspaceStatusPanel")
        workspace_summary_layout = QVBoxLayout(workspace_summary_panel)
        workspace_summary_layout.setContentsMargins(16, 14, 16, 14)
        workspace_summary_layout.setSpacing(6)
        workspace_summary_layout.addWidget(self.workspace_mode_label)
        workspace_summary_layout.addWidget(self.draft_status_label)

        workspace_detail_panel = QWidget()
        workspace_detail_panel.setObjectName("workspaceStatusPanel")
        workspace_detail_layout = QVBoxLayout(workspace_detail_panel)
        workspace_detail_layout.setContentsMargins(16, 14, 16, 14)
        workspace_detail_layout.setSpacing(6)
        workspace_detail_layout.addWidget(self.draft_change_label)
        workspace_detail_layout.addWidget(self.workspace_action_hint_label)

        workspace_actions_panel = QWidget()
        workspace_actions_panel.setObjectName("workspaceActionPanel")
        workspace_actions_layout = QVBoxLayout(workspace_actions_panel)
        workspace_actions_layout.setContentsMargins(0, 0, 0, 0)
        workspace_actions_layout.setSpacing(10)
        workspace_actions_layout.addWidget(self.new_analysis_button)
        workspace_actions_layout.addWidget(self.workspace_exit_button)
        workspace_actions_layout.addStretch(1)

        workspace_toolbar_row.addWidget(workspace_summary_panel, 4, Qt.AlignTop)
        workspace_toolbar_row.addWidget(workspace_detail_panel, 5, Qt.AlignTop)
        workspace_toolbar_row.addWidget(workspace_actions_panel, 0, Qt.AlignTop)
        workspace_toolbar_card.body_layout.addLayout(workspace_toolbar_row)

        self.result_view = StructuredResultView(
            "初次分析后，这里会展示草稿结果、风险点和原始 JSON。"
        )
        result_card = SectionCard("分析结果", "输出结构化测试范围，供你在草稿阶段反复完善。")
        result_card.body_layout.addWidget(self.result_view)

        self.open_questions_preview = QPlainTextEdit()
        self.open_questions_preview.setReadOnly(True)
        self.open_questions_preview.setPlaceholderText("分析完成后，这里会展示待确认项。")
        configure_text_input(self.open_questions_preview, min_width=360, min_height=120)
        self.open_questions_section = CollapsibleSection(
            "待确认项",
            "分析完成后可展开查看",
            expanded=False,
        )
        self.open_questions_section.body_layout.addWidget(self.open_questions_preview)

        self.refinement_input = QPlainTextEdit()
        self.refinement_input.setPlaceholderText("例如：补充角色限制、异常规则、接口文档地址、页面交互差异等。")
        configure_text_input(self.refinement_input, min_width=360, min_height=120)
        self.refine_button = build_secondary_button("继续完善")
        self.refine_button.clicked.connect(self._refine_requirement)

        refine_card = SectionCard("继续补充", "先补充新信息，再在需要时展开查看待确认项和设计建议。")
        refine_card.body_layout.addWidget(self.open_questions_section)
        refine_card.body_layout.addWidget(build_form_label("本轮补充"))
        refine_card.body_layout.addWidget(self.refinement_input)
        refine_card.body_layout.addWidget(self.refine_button)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(form_card)
        left_layout.addWidget(refine_card)
        left_layout.addWidget(self.guide_section)
        left_layout.addStretch(1)

        self.scenario_table = ScenarioHandoffList()
        self.selection_summary_label = QLabel(
            "以下是根据当前需求整理出的测试场景，请逐项确认覆盖范围，并选择后续处理方式。"
        )
        self.selection_summary_label.setWordWrap(True)
        self.confirm_handoff_button = build_secondary_button("确认场景处理方式")
        self.confirm_handoff_button.clicked.connect(self._confirm_draft_handoff)
        self.confirm_handoff_button.setMinimumWidth(260)
        self.confirm_handoff_button.setMaximumWidth(320)

        handoff_card = SectionCard(
            "测试场景",
            "以下是根据当前需求整理出的测试场景，请逐项确认覆盖范围，并选择后续处理方式。",
        )
        handoff_card.body_layout.addWidget(self.selection_summary_label)
        handoff_card.body_layout.addWidget(self.scenario_table)
        handoff_action_row = QHBoxLayout()
        handoff_action_row.setContentsMargins(0, 0, 0, 0)
        handoff_action_row.setSpacing(10)
        handoff_action_row.addStretch(1)
        handoff_action_row.addWidget(self.confirm_handoff_button)
        handoff_action_row.addWidget(self.confirm_save_button)
        handoff_card.body_layout.addLayout(handoff_action_row)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(18)
        right_layout.addWidget(result_card)
        right_layout.addWidget(handoff_card)
        right_layout.addStretch(1)

        self.page_splitter.addWidget(left_panel)
        self.page_splitter.addWidget(right_panel)
        self.page_splitter.setStretchFactor(0, 4)
        self.page_splitter.setStretchFactor(1, 5)

        analysis_tab = QWidget()
        analysis_tab_layout = QVBoxLayout(analysis_tab)
        analysis_tab_layout.setContentsMargins(0, 0, 0, 0)
        analysis_tab_layout.addWidget(workspace_toolbar_card)
        analysis_tab_layout.addWidget(self.page_splitter)

        self.record_search_input = QLineEdit()
        self.record_search_input.setPlaceholderText("按标题或摘要筛选已保存记录")
        self.record_search_input.textChanged.connect(self._handle_record_filter_changed)
        configure_line_input(self.record_search_input, min_width=220, min_height=48)

        self.refresh_records_button = build_secondary_button("刷新记录")
        self.refresh_records_button.clicked.connect(self._refresh_requirement_records)
        self.record_count_label = QLabel("暂无已保存的需求分析记录。")
        self.record_count_label.setWordWrap(True)

        self.record_list = QListWidget()
        self.record_list.setObjectName("requirementRecordList")
        self.record_list.setSpacing(6)
        self.record_list.currentItemChanged.connect(self._handle_record_selection_changed)

        record_toolbar = QHBoxLayout()
        record_toolbar.setContentsMargins(0, 0, 0, 0)
        record_toolbar.setSpacing(10)
        record_toolbar.addWidget(self.record_search_input, 1)
        record_toolbar.addWidget(self.refresh_records_button)

        record_list_card = SectionCard("需求记录", "这里只展示已经确认保存的正式记录。")
        record_list_card.body_layout.addLayout(record_toolbar)
        record_list_card.body_layout.addWidget(self.record_count_label)
        record_list_card.body_layout.addWidget(self.record_list)

        self.record_meta_label = QLabel("请选择左侧记录，查看历史分析详情。")
        self.record_meta_label.setWordWrap(True)
        self.record_result_view = StructuredResultView(
            "选中左侧记录后，这里会展示正式保存的分析摘要和原始 JSON。"
        )
        self.record_requirement_preview = QPlainTextEdit()
        self.record_requirement_preview.setReadOnly(True)
        self.record_requirement_preview.setPlaceholderText("这里会显示原始需求快照和完善轨迹。")
        configure_text_input(self.record_requirement_preview, min_width=360, min_height=180)

        self.load_record_button = build_secondary_button("继续完善此记录")
        self.load_record_button.clicked.connect(self._load_selected_record_into_analysis_tab)
        self.load_record_button.setEnabled(False)
        self.delete_record_button = build_secondary_button("删除记录")
        self.delete_record_button.clicked.connect(self._delete_selected_record)
        self.delete_record_button.setEnabled(False)

        record_action_row = QHBoxLayout()
        record_action_row.setContentsMargins(0, 0, 0, 0)
        record_action_row.setSpacing(10)
        record_action_row.addWidget(self.load_record_button)
        record_action_row.addWidget(self.delete_record_button)
        record_action_row.addStretch(1)

        record_detail_card = SectionCard("记录详情", "可查看正式记录详情，或载入到草稿区继续完善。")
        record_detail_card.body_layout.addWidget(self.record_meta_label)
        record_detail_card.body_layout.addLayout(record_action_row)
        record_detail_card.body_layout.addWidget(self.record_result_view)
        record_detail_card.body_layout.addWidget(build_form_label("原始需求快照 / 完善轨迹"))
        record_detail_card.body_layout.addWidget(self.record_requirement_preview)

        self.record_splitter = QSplitter(Qt.Horizontal)
        self.record_splitter.setChildrenCollapsible(False)
        self.record_splitter.addWidget(record_list_card)
        self.record_splitter.addWidget(record_detail_card)
        self.record_splitter.setStretchFactor(0, 3)
        self.record_splitter.setStretchFactor(1, 5)

        management_tab = QWidget()
        management_tab_layout = QVBoxLayout(management_tab)
        management_tab_layout.setContentsMargins(0, 0, 0, 0)
        management_tab_layout.addWidget(self.record_splitter)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("requirementTabs")
        self.tab_widget.addTab(analysis_tab, "分析需求")
        self.tab_widget.addTab(management_tab, "需求记录")
        self.tab_widget.currentChanged.connect(self._handle_tab_changed)

        layout.addWidget(self.tab_widget)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scaffold)
        self._apply_responsive_layout(self.width())
        self._sync_action_states()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout(event.size().width())

    def _apply_responsive_layout(self, width: int) -> None:
        # 需求分析页的信息密度高，窗口变窄时改成上下编排，比继续强行双栏更稳定也更易操作。
        analysis_vertical = width < self.ANALYSIS_VERTICAL_BREAKPOINT
        self.page_splitter.setOrientation(Qt.Vertical if analysis_vertical else Qt.Horizontal)
        if analysis_vertical:
            self.page_splitter.setSizes([max(int(width * 0.55), 520), max(int(width * 0.45), 420)])
        else:
            self.page_splitter.setSizes([max(int(width * 0.46), 420), max(int(width * 0.54), 460)])

        records_vertical = width < self.RECORDS_VERTICAL_BREAKPOINT
        self.record_splitter.setOrientation(Qt.Vertical if records_vertical else Qt.Horizontal)
        if records_vertical:
            self.record_splitter.setSizes([max(int(width * 0.34), 260), max(int(width * 0.66), 420)])
        else:
            self.record_splitter.setSizes([max(int(width * 0.36), 320), max(int(width * 0.64), 480)])

    def _pick_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择截图",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if files:
            self.images_input.setText(",".join(files))

    def _load_business_categories(self) -> None:
        try:
            self.business_categories = self.controller.list_business_categories()
        except Exception as exc:
            self.business_categories = []
            show_error_dialog(self, title="加载业务分类失败", message=str(exc))
        self._populate_business_level1_options()

    def _restore_active_draft_from_store(self) -> None:
        draft = self.controller.get_active_requirement_draft()
        if draft is None:
            self._render_empty_workspace()
            return
        self._load_draft_into_workspace(draft, status="已恢复未保存草稿")

    def _populate_business_level1_options(
        self,
        *,
        selected_level1_code: str = "",
        selected_level1_name: str = "",
        selected_level2_code: str = "",
        selected_level2_name: str = "",
    ) -> None:
        # 需求分析页直接复用统一业务字典，保证保存下来的业务归属可被后续模块稳定复用。
        self.business_level1_input.blockSignals(True)
        self.business_level1_input.clear()
        self.business_level1_input.addItem("请选择一级业务分类（可选）", "")
        for category in self.business_categories:
            self.business_level1_input.addItem(category.name, category.code)
        if selected_level1_code and self._find_combo_index(self.business_level1_input, selected_level1_code) == 0:
            self.business_level1_input.addItem(selected_level1_name or selected_level1_code, selected_level1_code)

        target_index = self._find_combo_index(self.business_level1_input, selected_level1_code)
        self.business_level1_input.setCurrentIndex(target_index)
        self.business_level1_input.setEnabled(bool(self.business_categories) or bool(selected_level1_code))
        self.business_level1_input.blockSignals(False)
        self._populate_business_level2_options(
            level1_code=self.business_level1_input.currentData() or "",
            selected_level2_code=selected_level2_code,
            selected_level2_name=selected_level2_name,
        )

    def _populate_business_level2_options(
        self,
        *,
        level1_code: str,
        selected_level2_code: str = "",
        selected_level2_name: str = "",
    ) -> None:
        self.business_level2_input.blockSignals(True)
        self.business_level2_input.clear()

        category = self._find_business_category(level1_code)
        if not level1_code:
            self.business_level2_input.addItem("请先选择一级业务分类", "")
            self.business_level2_input.setEnabled(False)
        elif category is None:
            self.business_level2_input.addItem(selected_level2_name or selected_level2_code or "历史二级业务分类", selected_level2_code)
            self.business_level2_input.setEnabled(bool(selected_level2_code))
        elif not category.children:
            self.business_level2_input.addItem("当前一级业务未配置二级分类", "")
            self.business_level2_input.setEnabled(False)
        else:
            self.business_level2_input.addItem("请选择二级业务分类（可选）", "")
            for child in category.children:
                self.business_level2_input.addItem(child.name, child.code)
            if selected_level2_code and self._find_combo_index(self.business_level2_input, selected_level2_code) == 0:
                self.business_level2_input.addItem(selected_level2_name or selected_level2_code, selected_level2_code)
            target_index = self._find_combo_index(self.business_level2_input, selected_level2_code)
            self.business_level2_input.setCurrentIndex(target_index)
            self.business_level2_input.setEnabled(True)

        self.business_level2_input.blockSignals(False)

    def _handle_business_level1_changed(self, _index: int) -> None:
        self._populate_business_level2_options(level1_code=self.business_level1_input.currentData() or "")

    @staticmethod
    def _find_combo_index(combo_box: AppSelect, target_value: str) -> int:
        if not target_value:
            return 0
        for index in range(combo_box.count()):
            if combo_box.itemData(index) == target_value:
                return index
        return 0

    def _find_business_category(self, level1_code: str) -> BusinessCategory | None:
        for category in self.business_categories:
            if category.code == level1_code:
                return category
        return None

    def _selected_business_category_payload(self) -> dict[str, str]:
        level1_code = self.business_level1_input.currentData() or ""
        level1_name = self.business_level1_input.currentText().strip() if level1_code else ""
        level2_code = self.business_level2_input.currentData() or ""
        level2_name = self.business_level2_input.currentText().strip() if level2_code else ""
        return {
            "business_level1_code": level1_code,
            "business_level1_name": level1_name,
            "business_level2_code": level2_code,
            "business_level2_name": level2_name,
        }

    def _populate_detail_level_options(self) -> None:
        self.scenario_detail_level_input.clear()
        self.scenario_detail_level_input.addItem("核心主链路", ScenarioDetailLevel.BRIEF.value)
        self.scenario_detail_level_input.addItem("标准测试", ScenarioDetailLevel.STANDARD.value)
        self.scenario_detail_level_input.addItem("完整覆盖", ScenarioDetailLevel.DETAILED.value)
        self.scenario_detail_level_input.setCurrentIndex(1)

    def _handle_tab_changed(self, index: int) -> None:
        if index == 1:
            self._refresh_requirement_records()

    def _handle_record_filter_changed(self, _text: str) -> None:
        self._render_requirement_records()

    def _refresh_requirement_records(self) -> None:
        self.refresh_records_button.setEnabled(False)
        try:
            records = self.controller.list_requirement_records()
        except Exception as exc:
            self._show_requirement_record_error(str(exc))
            return
        self._show_requirement_records(records)

    def _show_requirement_records(self, records) -> None:
        self.refresh_records_button.setEnabled(True)
        self.record_summaries = records
        self._render_requirement_records(preferred_requirement_id=self.selected_record_id)

    def _show_requirement_record_error(self, message: str) -> None:
        self.refresh_records_button.setEnabled(True)
        show_error_dialog(self, title="加载需求记录失败", message=message)

    def _render_requirement_records(self, *, preferred_requirement_id: str | None = None) -> None:
        keyword = self.record_search_input.text().strip().lower()
        filtered = [
            item
            for item in self.record_summaries
            if not keyword
            or keyword in item.title.lower()
            or keyword in item.summary.lower()
            or keyword in item.business_path.lower()
        ]

        self.record_list.blockSignals(True)
        self.record_list.clear()
        selected_item: QListWidgetItem | None = None
        for record in filtered:
            item = QListWidgetItem(self._build_record_list_text(record))
            item.setData(Qt.UserRole, record.requirement_id)
            item.setSizeHint(QSize(0, 62))
            item.setToolTip(record.summary or record.title)
            self.record_list.addItem(item)
            if preferred_requirement_id and record.requirement_id == preferred_requirement_id:
                selected_item = item

        self.record_count_label.setText(
            f"共找到 {len(filtered)} 条记录。"
            if filtered
            else "暂无匹配的需求分析记录。"
        )
        self.record_list.blockSignals(False)

        if not filtered:
            self._clear_record_detail()
            return

        if selected_item is not None:
            self.record_list.setCurrentItem(selected_item)
            return
        if self.record_list.currentItem() is None:
            self.record_list.setCurrentRow(0)

    def _build_record_list_text(self, record) -> str:
        generated_at = record.generated_at.astimezone().strftime("%Y-%m-%d %H:%M") if record.generated_at else "-"
        handoff_text = "已保存去向" if record.handoff_saved else "未保存去向"
        return (
            f"{record.title}\n"
            f"{generated_at} · {record.source}"
            f"{f' · {record.business_path}' if record.business_path else ''}"
            f" · 场景 {record.scenario_count} 个 · {handoff_text}"
        )

    def _handle_record_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self.selected_record_id = None
            self.current_record = None
            self._clear_record_detail()
            return
        requirement_id = current.data(Qt.UserRole)
        if not requirement_id:
            self._clear_record_detail()
            return

        self.selected_record_id = requirement_id
        self.current_record = None
        self.load_record_button.setEnabled(False)
        self.delete_record_button.setEnabled(False)
        self.record_result_view.set_loading("正在加载需求记录，请稍候...")
        try:
            record = self.controller.get_requirement_record(requirement_id)
        except Exception as exc:
            self._show_record_detail_error(str(exc))
            return
        self._show_record_detail(record)

    def _show_record_detail(self, record) -> None:
        self.current_record = record
        self.selected_record_id = record.requirement.id
        self.load_record_button.setEnabled(True)
        self.delete_record_button.setEnabled(True)

        handoff_text = self._build_handoff_summary_text(record.analysis, record.handoff)
        business_text = record.requirement.business_path or "未分类"
        self.record_meta_label.setText(
            f"标题：{record.requirement.title}\n"
            f"来源：{record.requirement.source} · 业务归属：{business_text}\n"
            f"创建时间：{record.requirement.created_at.astimezone().strftime('%Y-%m-%d %H:%M')}\n"
            f"分析时间：{record.analysis.generated_at.astimezone().strftime('%Y-%m-%d %H:%M')} · "
            f"测试场景：{len(record.analysis.scenarios)} 个 · 完善轮次：{len(record.refinement_history)}\n"
            f"{handoff_text}"
        )
        self._render_result_view(
            self.record_result_view,
            record.analysis,
            status="已保存需求记录",
        )
        self.record_requirement_preview.setPlainText(
            self._build_requirement_snapshot(record.requirement, record.refinement_history)
        )

    def _show_record_detail_error(self, message: str) -> None:
        self._clear_record_detail()
        show_error_dialog(self, title="加载记录详情失败", message=message)

    def _clear_record_detail(self) -> None:
        self.current_record = None
        self.load_record_button.setEnabled(False)
        self.delete_record_button.setEnabled(False)
        self.record_meta_label.setText("请选择左侧记录，查看历史分析详情。")
        self.record_result_view.set_placeholder()
        self.record_requirement_preview.setPlainText("")

    def _analyze_requirement(self) -> None:
        if self.current_draft is not None:
            confirmed = ask_confirmation(
                self,
                title="覆盖当前草稿",
                message="重新做初次分析会覆盖当前未保存草稿，是否继续？",
                confirm_text="继续覆盖",
            )
            if not confirmed:
                return

        requirement = self._build_requirement_input(preserve_existing_id=False)
        self.result_view.set_loading("正在生成需求分析草稿，请稍候...", show_thinking_feedback=True)
        on_success, on_error = begin_async_button_feedback(
            self.initial_analyze_button,
            busy_text="分析中...",
            on_success=self._show_draft_started,
            on_error=self._show_analysis_error,
            disable_widgets=[self.new_analysis_button, self.workspace_exit_button],
        )
        self.runner.submit(
            self.controller.start_requirement_analysis,
            requirement,
            on_success=on_success,
            on_error=on_error,
        )

    def _start_new_requirement_analysis(self) -> None:
        if self.current_draft is None and self.current_record is None and not self._has_workspace_content():
            self._render_empty_workspace(clear_form=True)
            return

        if self.current_draft is not None:
            mode_label = (
                "当前正在编辑一条已保存记录。"
                if self.current_draft.source is RequirementDraftSource.RECORD_EDIT
                else "当前存在一份未保存草稿。"
            )
        elif self.current_record is not None:
            mode_label = "当前页展示的是一条已保存记录。"
        else:
            mode_label = "当前输入区已有内容。"

        confirmed = ask_confirmation(
            self,
            title="开始新的需求分析",
            message=f"{mode_label} 开始新的需求分析会清空当前工作区，是否继续？",
            confirm_text="确认新建",
        )
        if not confirmed:
            return

        if self.current_draft is not None:
            self.controller.discard_requirement_draft()
        self.current_record = None
        self.selected_record_id = None
        self._render_empty_workspace(clear_form=True)

    def _show_draft_started(self, draft) -> None:
        self.refinement_input.setPlainText("")
        self._load_draft_into_workspace(draft, status="草稿已生成，待继续完善或确认保存")

    def _show_analysis_error(self, message: str) -> None:
        self._sync_action_states()
        self.result_view.set_result(
            status="需求分析失败",
            metrics=[],
            summary_html=f"<h3>失败原因</h3><p>{escape(message)}</p>",
            payload=None,
        )
        show_error_dialog(self, title="需求分析失败", message=message)

    def _refine_requirement(self) -> None:
        if not self._ensure_active_draft_available(action_label="继续完善"):
            return
        if self.current_draft is None or self.current_draft.latest_analysis is None:
            show_warning_dialog(self, title="无法继续完善", message="请先完成初次分析，生成一个需求草稿。")
            return

        user_input = self.refinement_input.toPlainText().strip()
        if not user_input:
            show_warning_dialog(self, title="缺少补充说明", message="请先输入本轮补充说明。")
            return

        requirement = self._build_requirement_input(preserve_existing_id=True)
        self.result_view.set_loading("正在根据补充说明更新草稿，请稍候...", show_thinking_feedback=True)
        on_success, on_error = begin_async_button_feedback(
            self.refine_button,
            busy_text="完善中...",
            on_success=self._show_draft_refined,
            on_error=self._show_refine_error,
            disable_widgets=[self.confirm_handoff_button, self.confirm_save_button],
        )
        self.runner.submit(
            self.controller.refine_requirement_analysis,
            requirement=requirement,
            user_input=user_input,
            on_success=on_success,
            on_error=on_error,
        )

    def _show_draft_refined(self, draft) -> None:
        # 重算后草稿里的场景处理方式会被重置，因此这里清空本轮补充框并提示用户重新确认。
        self.refinement_input.setPlainText("")
        self._load_draft_into_workspace(draft, status="草稿已更新，待重新确认场景处理方式")

    def _show_refine_error(self, message: str) -> None:
        self._sync_action_states()
        self.result_view.set_result(
            status="继续完善失败",
            metrics=[],
            summary_html=f"<h3>失败原因</h3><p>{escape(message)}</p>",
            payload=None,
        )
        show_error_dialog(self, title="继续完善失败", message=message)

    def _confirm_draft_handoff(self) -> None:
        if not self._ensure_active_draft_available(action_label="确认场景处理方式"):
            return
        if self.current_draft is None or self.current_draft.latest_analysis is None:
            show_warning_dialog(self, title="无法确认", message="请先完成需求分析，再确认场景处理方式。")
            return
        if self._has_unsaved_form_changes():
            show_warning_dialog(
                self,
                title="请先重新分析",
                message="输入区内容已修改但尚未重新分析，请先继续完善后再确认场景处理方式。",
            )
            return

        on_success, on_error = begin_async_button_feedback(
            self.confirm_handoff_button,
            busy_text="确认中...",
            on_success=self._show_draft_handoff_saved,
            on_error=self._show_handoff_error,
            disable_widgets=[self.confirm_save_button],
        )
        self.runner.submit(
            self.controller.save_requirement_draft_handoff,
            scenario_statuses=self._scenario_statuses(),
            on_success=on_success,
            on_error=on_error,
        )

    def _show_draft_handoff_saved(self, draft) -> None:
        self.current_draft = draft
        self._refresh_selection_summary()
        self._update_draft_status(status="当前场景处理方式已确认，可保存正式记录")
        self._sync_action_states()

    def _show_handoff_error(self, message: str) -> None:
        self._sync_action_states()
        show_error_dialog(self, title="确认场景处理方式失败", message=message)

    def _confirm_save_draft(self) -> None:
        if not self._ensure_active_draft_available(action_label="保存正式记录"):
            return
        if self.current_draft is None or self.current_draft.latest_analysis is None:
            show_warning_dialog(self, title="无法保存", message="当前没有可保存的需求草稿。")
            return
        if self._has_unsaved_form_changes():
            show_warning_dialog(
                self,
                title="请先重新分析",
                message="输入区内容已修改但尚未重新分析，请先继续完善后再保存正式记录。",
            )
            return
        if not self.current_draft.handoff_confirmed:
            show_warning_dialog(
                self,
                title="场景处理方式未确认",
                message="请先确认场景处理方式，再保存正式记录。",
            )
            return

        confirmed = ask_confirmation(
            self,
            title="确认保存正式记录",
            message="保存后会生成或覆盖正式需求记录，并清除当前活动草稿，是否继续？",
            confirm_text="确认保存",
        )
        if not confirmed:
            return

        on_success, on_error = begin_async_button_feedback(
            self.confirm_save_button,
            busy_text="保存中...",
            on_success=self._show_draft_saved,
            on_error=self._show_save_error,
            disable_widgets=[self.confirm_handoff_button, self.refine_button],
        )
        self.runner.submit(
            self.controller.confirm_requirement_draft,
            on_success=on_success,
            on_error=on_error,
        )

    def _show_draft_saved(self, record) -> None:
        continue_editing_saved_record = (
            self.current_draft is not None
            and self.current_draft.source is RequirementDraftSource.RECORD_EDIT
        )
        self.current_draft = None
        self.current_record = record
        self.workspace_requirement_id = record.requirement.id
        self._refresh_requirement_records()
        self.selected_record_id = record.requirement.id
        self.refinement_input.setPlainText("")

        if continue_editing_saved_record:
            # 从正式记录进入编辑态时，保存成功后应继续停留在当前编辑上下文，避免用户再回记录页重新载入。
            refreshed_draft = self.controller.create_requirement_draft_from_record(record.requirement.id)
            self._load_draft_into_workspace(
                refreshed_draft,
                status="正式记录已保存，当前仍处于编辑模式",
            )
        else:
            self._apply_requirement_to_form(record.requirement)
            self._render_result_view(self.result_view, record.analysis, status="已保存正式记录")
            self._set_open_questions_text(record.analysis.open_questions)
            self._populate_scenario_table(record.analysis.scenarios, record.handoff)
            self._update_draft_status(status="正式记录已保存。如需继续完善，请从需求记录中重新载入。")
            self._sync_action_states()

        show_info_dialog(self, title="保存成功", message="当前需求草稿已保存为正式记录。")

    def _show_save_error(self, message: str) -> None:
        self._sync_action_states()
        show_error_dialog(self, title="保存正式记录失败", message=message)

    def _discard_draft(self) -> None:
        if self.current_draft is None and self.current_record is None and not self._has_workspace_content():
            self._render_empty_workspace(clear_form=True)
            return

        if self.current_draft and self.current_draft.source is RequirementDraftSource.RECORD_EDIT:
            title = "退出编辑"
            message = "退出后会结束当前记录的编辑态，并保留已保存内容。是否继续？"
            confirm_text = "确认退出"
        elif self.current_draft is not None:
            title = "放弃草稿"
            message = "放弃后会清除当前活动草稿及本地恢复状态，是否继续？"
            confirm_text = "确认放弃"
        elif self.current_record is not None:
            title = "返回新建态"
            message = "返回后会退出当前记录查看状态，并清空当前工作区。是否继续？"
            confirm_text = "确认返回"
        else:
            title = "清空工作区"
            message = "清空后会移除当前输入区内容。是否继续？"
            confirm_text = "确认清空"

        confirmed = ask_confirmation(
            self,
            title=title,
            message=message,
            confirm_text=confirm_text,
        )
        if not confirmed:
            return

        if self.current_draft is not None:
            self.controller.discard_requirement_draft()
        self.current_record = None
        self.selected_record_id = None
        self._render_empty_workspace(clear_form=True)

    def _populate_scenario_table(self, scenarios: list, handoff=None) -> None:
        self.scenario_status_groups = {}
        self.displayed_scenarios = self._sort_scenarios_by_priority(scenarios)
        self.scenario_table.clear_rows()
        for scenario in self.displayed_scenarios:
            status_selector, button_group = self._build_status_selector()
            self.scenario_table.add_row(
                scenario_id=scenario.scenario_id,
                title=scenario.title,
                detail=(
                    f"{scenario.module} · {scenario.automation_type.value.upper()} · "
                    f"{self.SCENARIO_KIND_LABELS.get(scenario.scenario_kind, '未分类')}"
                ),
                priority=scenario.priority.value,
                summary=scenario.summary,
                step_preview=scenario.steps[:2],
                assertion_preview=scenario.assertions[:2],
                actions=status_selector,
            )
            self.scenario_status_groups[scenario.scenario_id] = button_group

        self._restoring_scenario_statuses = True
        self._apply_saved_handoff(handoff)
        self._restoring_scenario_statuses = False
        self._refresh_selection_summary()
        self._sync_action_states()

    def _build_status_selector(self) -> tuple[QWidget, QButtonGroup]:
        container = QWidget()
        container.setObjectName("scenarioHandoffSelector")
        container.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        container.setFixedHeight(34)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        button_group = QButtonGroup(container)
        button_group.setExclusive(True)
        for index, (status, label) in enumerate(self.STATUS_LABELS.items()):
            button = QPushButton(label)
            button.setProperty("role", "statusChoice")
            button.setCheckable(True)
            button.setMinimumWidth(88)
            button.setFixedHeight(30)
            button.setCursor(Qt.PointingHandCursor)
            button.style().unpolish(button)
            button.style().polish(button)
            layout.addWidget(button)
            button_group.addButton(button)
            button_group.setId(button, index)
            button.toggled.connect(self._handle_scenario_status_toggled)
            button.setProperty("statusValue", status.value)
            if status is ScenarioHandoffStatus.AUTOMATION:
                button.setChecked(True)
        layout.addStretch(1)
        return container, button_group

    def _handle_scenario_status_toggled(self, checked: bool) -> None:
        if not checked:
            return
        if not self._restoring_scenario_statuses and self.current_draft is not None:
            self.current_draft = self.current_draft.model_copy(update={"handoff_confirmed": False})
            self._update_draft_status(status="场景处理方式已变更，请重新确认场景处理方式")
        self._refresh_selection_summary()
        self._sync_action_states()

    def _scenario_statuses(self) -> dict[str, str]:
        scenario_statuses: dict[str, str] = {}
        for scenario_id, button_group in self.scenario_status_groups.items():
            checked_button = button_group.checkedButton()
            if checked_button is not None:
                scenario_statuses[scenario_id] = checked_button.property("statusValue")
        return scenario_statuses

    def _status_counts(self) -> dict[ScenarioHandoffStatus, int]:
        counts = {status: 0 for status in ScenarioHandoffStatus}
        for status_value in self._scenario_statuses().values():
            counts[ScenarioHandoffStatus(status_value)] += 1
        return counts

    def _priority_counts(self) -> dict[ScenarioPriority, int]:
        counts = {priority: 0 for priority in ScenarioPriority}
        for scenario in self.displayed_scenarios:
            counts[scenario.priority] += 1
        return counts

    def _refresh_selection_summary(self) -> None:
        priority_counts = self._priority_counts()
        status_counts = self._status_counts()
        total = sum(status_counts.values())
        if total == 0:
            self.selection_summary_label.setText(
                "以下是根据当前需求整理出的测试场景，请逐项确认覆盖范围，并选择后续处理方式。"
            )
            return

        suffix = "当前处理方式已确认。" if self.current_draft and self.current_draft.handoff_confirmed else "当前处理方式尚未确认。"
        self.selection_summary_label.setText(
            f"当前共识别 {total} 个测试场景：P0 {priority_counts[ScenarioPriority.P0]} 个，"
            f"P1 {priority_counts[ScenarioPriority.P1]} 个，"
            f"P2 {priority_counts[ScenarioPriority.P2]} 个，"
            f"P3 {priority_counts[ScenarioPriority.P3]} 个。"
            f" 纳入自动化 {status_counts[ScenarioHandoffStatus.AUTOMATION]} 个，"
            f"仅做回归 {status_counts[ScenarioHandoffStatus.REGRESSION_ONLY]} 个，"
            f"暂不处理 {status_counts[ScenarioHandoffStatus.DEFERRED]} 个。{suffix}"
        )

    def _load_selected_record_into_analysis_tab(self) -> None:
        if self.current_record is None:
            return
        if self.current_draft is not None:
            confirmed = ask_confirmation(
                self,
                title="替换当前草稿",
                message="继续完善这条记录会覆盖当前未保存草稿，是否继续？",
                confirm_text="继续载入",
            )
            if not confirmed:
                return

        try:
            draft = self.controller.create_requirement_draft_from_record(self.current_record.requirement.id)
        except Exception as exc:
            self._show_record_draft_error(str(exc))
            return

        self.refinement_input.setPlainText("")
        self._load_draft_into_workspace(draft, status="已载入正式记录，可继续完善")
        self.tab_widget.setCurrentIndex(0)

    def _show_record_draft_error(self, message: str) -> None:
        show_error_dialog(self, title="载入记录到草稿区失败", message=message)

    def _delete_selected_record(self) -> None:
        if self.selected_record_id is None:
            return
        confirmed = ask_confirmation(
            self,
            title="删除需求记录",
            message="删除后将移除该需求的分析结果、测试场景处理方式、完善轨迹和场景索引，是否继续？",
            confirm_text="确认删除",
        )
        if not confirmed:
            return

        requirement_id = self.selected_record_id
        self.load_record_button.setEnabled(False)
        self.delete_record_button.setEnabled(False)
        try:
            self.controller.delete_requirement_record(requirement_id)
        except Exception as exc:
            self._show_record_delete_error(str(exc))
            return
        self._show_record_deleted(requirement_id)

    def _show_record_deleted(self, requirement_id: str) -> None:
        if self.current_record is not None and self.current_record.requirement.id == requirement_id:
            self._clear_record_detail()
        if self.workspace_requirement_id == requirement_id and self.current_draft is None:
            self._render_empty_workspace(clear_form=True)
        self.record_summaries = [
            item for item in self.record_summaries if item.requirement_id != requirement_id
        ]
        self.selected_record_id = None
        self._render_requirement_records()
        self._refresh_requirement_records()

    def _show_record_delete_error(self, message: str) -> None:
        self.load_record_button.setEnabled(self.current_record is not None)
        self.delete_record_button.setEnabled(self.current_record is not None)
        show_error_dialog(self, title="删除需求记录失败", message=message)

    def _load_draft_into_workspace(self, draft: RequirementAnalysisDraft, *, status: str) -> None:
        self.current_draft = draft
        self.workspace_requirement_id = draft.requirement.id
        self._apply_requirement_to_form(draft.requirement)
        if draft.latest_analysis is None:
            self.result_view.set_placeholder()
            self._set_open_questions_text([])
            self._populate_scenario_table([], None)
        else:
            self._render_result_view(self.result_view, draft.latest_analysis, status=status)
            self._set_open_questions_text(draft.latest_analysis.open_questions)
            self._populate_scenario_table(draft.latest_analysis.scenarios, draft.current_handoff)
        self._update_draft_status(status=status)
        self._sync_action_states()

    def _render_empty_workspace(self, *, clear_form: bool = False) -> None:
        self.current_draft = None
        self.workspace_requirement_id = None
        if clear_form:
            self._reset_form_inputs()
        self.result_view.set_placeholder()
        self._set_open_questions_text([])
        self.refinement_input.setPlainText("")
        self._populate_scenario_table([], None)
        self._update_draft_status(status="当前没有活动草稿。")
        self._sync_action_states()

    def _reset_form_inputs(self) -> None:
        self.title_input.setText("")
        self.source_input.setText("需求文档")
        self._populate_business_level1_options()
        self._populate_detail_level_options()
        self.images_input.setText("")
        self.notes_input.setText("")
        self.markdown_input.setPlainText("")

    def _apply_requirement_to_form(self, requirement) -> None:
        self.title_input.setText(requirement.title)
        self.source_input.setText(requirement.source)
        self._populate_business_level1_options(
            selected_level1_code=requirement.business_level1_code,
            selected_level1_name=requirement.business_level1_name,
            selected_level2_code=requirement.business_level2_code,
            selected_level2_name=requirement.business_level2_name,
        )
        self.images_input.setText(",".join(requirement.image_paths))
        self.notes_input.setText(requirement.notes)
        self.scenario_detail_level_input.setCurrentIndex(
            self._find_combo_index(
                self.scenario_detail_level_input,
                requirement.scenario_detail_level.value,
            )
        )
        self.markdown_input.setPlainText(requirement.markdown_content)

    def _build_requirement_input(self, *, preserve_existing_id: bool):
        requirement_id = None
        created_at = None
        if preserve_existing_id and self.current_draft is not None:
            requirement_id = self.current_draft.requirement.id
            created_at = self.current_draft.requirement.created_at
        return self.controller.create_requirement_input(
            title=self.title_input.text(),
            markdown_content=self.markdown_input.toPlainText(),
            image_paths=[item.strip() for item in self.images_input.text().split(",") if item.strip()],
            source=self.source_input.text(),
            notes=self.notes_input.text(),
            scenario_detail_level=self.scenario_detail_level_input.currentData() or ScenarioDetailLevel.STANDARD.value,
            requirement_id=requirement_id,
            created_at=created_at,
            **self._selected_business_category_payload(),
        )

    def _has_unsaved_form_changes(self) -> bool:
        if self.current_draft is None:
            return False
        current_requirement = self._build_requirement_input(preserve_existing_id=True)
        return (
            current_requirement.model_dump(mode="json")
            != self.current_draft.requirement.model_dump(mode="json")
        )

    def _has_workspace_content(self) -> bool:
        return any(
            [
                self.title_input.text().strip(),
                self.source_input.text().strip() and self.source_input.text().strip() != "需求文档",
                self.images_input.text().strip(),
                self.notes_input.text().strip(),
                self.markdown_input.toPlainText().strip(),
            ]
        )

    def _set_open_questions_text(self, open_questions: list) -> None:
        if not open_questions:
            self.open_questions_preview.setPlainText("当前没有额外待确认项。")
            return
        self.open_questions_preview.setPlainText(
            "\n\n".join(
                f"{index}. {item.question}\n原因：{item.reason}"
                for index, item in enumerate(open_questions, start=1)
            )
        )

    def _apply_saved_handoff(self, handoff) -> None:
        status_map: dict[str, str] = {}
        if handoff is not None and handoff.scenario_decisions:
            status_map = {
                item.scenario_id: item.status.value
                for item in handoff.scenario_decisions
            }
        for scenario_id, button_group in self.scenario_status_groups.items():
            status_value = status_map.get(scenario_id, ScenarioHandoffStatus.AUTOMATION.value)
            for button in button_group.buttons():
                if button.property("statusValue") == status_value:
                    button.setChecked(True)
                    break

    def _sync_action_states(self) -> None:
        has_draft = self.current_draft is not None and self.current_draft.latest_analysis is not None
        handoff_confirmed = bool(has_draft and self.current_draft and self.current_draft.handoff_confirmed)
        self._refresh_workspace_mode_ui()
        self.initial_analyze_button.setEnabled(True)
        self.refine_button.setEnabled(has_draft)
        # 场景处理方式一旦确认成功，当前按钮应立即退到不可点击状态；
        # 这样用户能直观看到“确认已完成，下一步应该去保存正式记录”。
        self.confirm_handoff_button.setEnabled(bool(has_draft and not handoff_confirmed))
        self.confirm_save_button.setEnabled(handoff_confirmed)
        self.workspace_exit_button.setEnabled(
            self.current_draft is not None
            or self.current_record is not None
            or self._has_workspace_content()
        )
        for button_group in self.scenario_status_groups.values():
            for button in button_group.buttons():
                button.setEnabled(has_draft)

    def _refresh_workspace_mode_ui(self) -> None:
        if self.current_draft is not None:
            handoff_confirmed = self.current_draft.handoff_confirmed
            if self.current_draft.source is RequirementDraftSource.RECORD_EDIT:
                self.workspace_mode_label.setText("当前模式：编辑已保存记录")
                self.confirm_save_button.setText("保存更新到当前记录")
                self.refine_button.setText("继续完善当前记录")
                self.confirm_handoff_button.setText(
                    "已确认本次处理方式" if handoff_confirmed else "确认本次场景处理方式"
                )
                self.workspace_exit_button.setText("退出编辑")
                self.workspace_action_hint_label.setText("当前正在编辑一条已保存记录。若要切到新需求，点右侧“新建需求分析”。")
            else:
                self.workspace_mode_label.setText("当前模式：新建草稿")
                self.confirm_save_button.setText("确认保存正式记录")
                self.refine_button.setText("继续完善")
                self.confirm_handoff_button.setText(
                    "已确认场景处理方式" if handoff_confirmed else "确认场景处理方式"
                )
                self.workspace_exit_button.setText("放弃草稿")
                self.workspace_action_hint_label.setText("当前存在一份未保存草稿。若要改做新需求，点右侧“新建需求分析”。")
            return

        if self.current_record is not None:
            self.workspace_mode_label.setText("当前模式：查看正式记录")
            self.workspace_action_hint_label.setText("当前页展示的是已保存记录。若要开始全新需求，点右侧“新建需求分析”。")
            self.workspace_exit_button.setText("返回新建态")
        else:
            self.workspace_mode_label.setText("当前模式：新建分析")
            self.workspace_action_hint_label.setText("开始全新需求时，先录入内容，再点“初次分析”；要清空当前工作区，可点右侧“新建需求分析”。")
            self.workspace_exit_button.setText("清空工作区")
        self.confirm_save_button.setText("确认保存正式记录")
        self.refine_button.setText("继续完善")
        self.confirm_handoff_button.setText("确认场景处理方式")

    def _ensure_active_draft_available(self, *, action_label: str) -> bool:
        if self.current_draft is None:
            return True

        active_draft = self.controller.get_active_requirement_draft()
        if active_draft is not None:
            return True

        # 正式记录保存后，后台活动草稿已经被清理；若页面仍保留旧状态，需要立刻回收到只读状态。
        self.current_draft = None
        self._update_draft_status(status="当前页展示的是已保存正式记录，若要继续调整，请先从需求记录重新载入。")
        self._refresh_selection_summary()
        self._sync_action_states()
        show_warning_dialog(
            self,
            title=f"无法{action_label}",
            message="当前活动草稿已结束。若要继续调整，请先到“需求记录”页重新载入该记录。",
        )
        return False

    def _update_draft_status(self, *, status: str) -> None:
        if self.current_draft is None:
            self.draft_status_label.setText(status)
            self.draft_change_label.setText("尚无草稿轮次记录。")
            return

        source_label = {
            RequirementDraftSource.NEW: "新建草稿",
            RequirementDraftSource.RECORD_EDIT: "正式记录继续完善",
        }[self.current_draft.source]
        handoff_text = "已确认" if self.current_draft.handoff_confirmed else "待确认"
        self.draft_status_label.setText(
            f"{status}\n"
            f"草稿来源：{source_label} · 场景处理方式：{handoff_text}\n"
            f"最后更新时间：{self.current_draft.last_updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
        )
        latest_round = self.current_draft.refinement_history[-1] if self.current_draft.refinement_history else None
        self.draft_change_label.setText(
            latest_round.change_summary if latest_round is not None else "尚无草稿轮次记录。"
        )

    def _render_result_view(self, target_view: StructuredResultView, result, *, status: str) -> None:
        target_view.set_result(
            status=status,
            metrics=[
                (str(len(result.features)), "功能点"),
                (str(len(result.scenarios)), "测试场景"),
                (str(sum(1 for item in result.scenarios if item.priority is ScenarioPriority.P0)), "P0"),
                (str(len(result.risks)), "风险项"),
                (str(len(result.open_questions)), "待确认"),
            ],
            summary_html=self._build_analysis_summary_html(result),
            payload=result.model_dump(mode="json"),
        )

    def _build_analysis_summary_html(self, result) -> str:
        return "\n".join(
            [
                f"<h3>总体摘要</h3><p>{escape(result.summary or '暂无摘要')}</p>",
                "<h3>优先级分布</h3><p>"
                f"P0 {sum(1 for item in result.scenarios if item.priority is ScenarioPriority.P0)} 个，"
                f"P1 {sum(1 for item in result.scenarios if item.priority is ScenarioPriority.P1)} 个，"
                f"P2 {sum(1 for item in result.scenarios if item.priority is ScenarioPriority.P2)} 个，"
                f"P3 {sum(1 for item in result.scenarios if item.priority is ScenarioPriority.P3)} 个。"
                "</p>",
                "<h3>核心功能点</h3><ul>"
                + "".join(f"<li>{escape(item.name)}：{escape(item.summary)}</li>" for item in result.features[:6])
                + "</ul>",
                "<h3>风险与待确认</h3><ul>"
                + "".join(
                    f"<li>{escape(item.title)}（{escape(item.level)}）：{escape(item.impact)}</li>"
                    for item in result.risks[:4]
                )
                + "".join(f"<li>待确认：{escape(item.question)}</li>" for item in result.open_questions[:4])
                + "</ul>",
            ]
        )

    def _build_handoff_summary_text(self, analysis, handoff) -> str:
        priority_counts = self._count_priorities(analysis.scenarios)
        if handoff is None:
            return (
                f"测试场景：P0 {priority_counts[ScenarioPriority.P0]} 个，"
                f"P1 {priority_counts[ScenarioPriority.P1]} 个，"
                f"P2 {priority_counts[ScenarioPriority.P2]} 个，"
                f"P3 {priority_counts[ScenarioPriority.P3]} 个。\n"
                f"测试场景处理方式：未单独确认，默认 {len(analysis.scenarios)} 个测试场景均视为纳入自动化。"
            )

        counts = {status: 0 for status in ScenarioHandoffStatus}
        if handoff.scenario_decisions:
            for item in handoff.scenario_decisions:
                counts[item.status] += 1
        else:
            counts[ScenarioHandoffStatus.AUTOMATION] = len(handoff.selected_scenario_ids)
        return (
            f"测试场景：P0 {priority_counts[ScenarioPriority.P0]} 个，"
            f"P1 {priority_counts[ScenarioPriority.P1]} 个，"
            f"P2 {priority_counts[ScenarioPriority.P2]} 个，"
            f"P3 {priority_counts[ScenarioPriority.P3]} 个。\n"
            "测试场景处理方式："
            f"纳入自动化 {counts[ScenarioHandoffStatus.AUTOMATION]} 个，"
            f"仅做回归 {counts[ScenarioHandoffStatus.REGRESSION_ONLY]} 个，"
            f"暂不处理 {counts[ScenarioHandoffStatus.DEFERRED]} 个。"
        )

    @staticmethod
    def _sort_scenarios_by_priority(scenarios: list) -> list:
        order = {
            ScenarioPriority.P0: 0,
            ScenarioPriority.P1: 1,
            ScenarioPriority.P2: 2,
            ScenarioPriority.P3: 3,
        }
        return sorted(scenarios, key=lambda item: (order.get(item.priority, 99), item.scenario_id))

    @staticmethod
    def _count_priorities(scenarios: list) -> dict[ScenarioPriority, int]:
        counts = {priority: 0 for priority in ScenarioPriority}
        for scenario in scenarios:
            counts[scenario.priority] += 1
        return counts

    def _build_requirement_snapshot(self, requirement, refinement_history) -> str:
        history_text = "无"
        if refinement_history:
            history_text = "\n\n".join(
                [
                    f"第 {item.round_index} 轮\n"
                    f"补充：{item.user_input or '初次分析'}\n"
                    f"摘要：{item.analysis_summary or '无'}\n"
                    f"变化：{item.change_summary or '无'}"
                    for item in refinement_history
                ]
            )

        parts = [
            "业务分类：",
            requirement.business_path or "未分类",
            "",
            "补充说明：",
            requirement.notes or "无",
            "",
            "图片路径：",
            "\n".join(requirement.image_paths) if requirement.image_paths else "无",
            "",
            "Markdown 原文：",
            requirement.markdown_content or "无",
            "",
            "完善轨迹：",
            history_text,
        ]
        return "\n".join(parts)
