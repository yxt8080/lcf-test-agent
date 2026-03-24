from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from local_test_agent.models import BusinessCategory, BusinessSubcategory
from local_test_agent.ui.widgets import (
    PageScaffold,
    SectionCard,
    StructuredResultView,
    ask_confirmation,
    build_form_label,
    build_primary_button,
    build_secondary_button,
    configure_form_layout,
    configure_line_input,
    show_error_dialog,
    show_info_dialog,
    show_warning_dialog,
)


class BusinessCategoryPage(QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.categories: list[BusinessCategory] = []
        self.selected_category_index: int | None = None
        self.selected_child_index: int | None = None
        self._build_ui()
        self._load_categories()

    def _build_ui(self) -> None:
        scaffold = PageScaffold(
            "业务分类管理",
            "独立维护统一业务归属字典，供需求、自动化、缺陷等模块直接选择，不再混入系统设置。",
            meta="分类中心",
        )
        layout = scaffold.content_layout
        page_splitter = QSplitter(Qt.Horizontal)
        page_splitter.setChildrenCollapsible(False)

        self.category_list = QListWidget()
        self.category_list.setObjectName("businessCategoryList")
        self.category_list.setSpacing(10)
        self.category_list.currentItemChanged.connect(self._handle_category_changed)
        self.child_list = QListWidget()
        self.child_list.setObjectName("businessSubcategoryList")
        self.child_list.setSpacing(10)
        self.child_list.currentItemChanged.connect(self._handle_child_changed)
        self.category_summary_label = QLabel()
        self.category_summary_label.setObjectName("businessCategoryListSummary")
        self.child_summary_label = QLabel()
        self.child_summary_label.setObjectName("businessCategoryListSummary")

        self.category_code_input = QLineEdit()
        self.category_name_input = QLineEdit()
        self.child_code_input = QLineEdit()
        self.child_name_input = QLineEdit()
        configure_line_input(self.category_code_input, min_width=360)
        configure_line_input(self.category_name_input, min_width=360)
        configure_line_input(self.child_code_input, min_width=360)
        configure_line_input(self.child_name_input, min_width=360)
        self.preview_view = StructuredResultView("这里会展示当前业务分类树和可供下游选择的叶子选项。")

        add_category_button = build_primary_button("新增一级分类")
        add_category_button.clicked.connect(self._add_category)
        delete_category_button = build_secondary_button("删除一级分类")
        delete_category_button.clicked.connect(self._delete_category)
        add_child_button = build_primary_button("新增二级分类")
        add_child_button.clicked.connect(self._add_child)
        delete_child_button = build_secondary_button("删除二级分类")
        delete_child_button.clicked.connect(self._delete_child)
        apply_category_button = build_secondary_button("应用一级编辑")
        apply_category_button.clicked.connect(self._apply_category_edit)
        apply_child_button = build_secondary_button("应用二级编辑")
        apply_child_button.clicked.connect(self._apply_child_edit)
        save_button = build_primary_button("保存全部变更")
        save_button.clicked.connect(self._save_all)
        reload_button = build_secondary_button("重新加载")
        reload_button.clicked.connect(self._load_categories)

        category_card = SectionCard("一级分类", "先选中一级业务，再维护对应的二级业务。")
        category_card.body_layout.addWidget(self.category_summary_label)
        category_card.body_layout.addWidget(self.category_list)
        category_action_row = QHBoxLayout()
        category_action_row.setContentsMargins(0, 0, 0, 0)
        category_action_row.setSpacing(10)
        category_action_row.addWidget(add_category_button)
        category_action_row.addWidget(delete_category_button)
        category_card.body_layout.addLayout(category_action_row)

        child_card = SectionCard("二级分类", "二级分类归属于当前选中的一级业务；不允许脱离父级单独存在。")
        child_card.body_layout.addWidget(self.child_summary_label)
        child_card.body_layout.addWidget(self.child_list)
        child_action_row = QHBoxLayout()
        child_action_row.setContentsMargins(0, 0, 0, 0)
        child_action_row.setSpacing(10)
        child_action_row.addWidget(add_child_button)
        child_action_row.addWidget(delete_child_button)
        child_card.body_layout.addLayout(child_action_row)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(category_card)
        left_layout.addWidget(child_card)

        editor_card = SectionCard("分类详情", "先在左侧选择分类，再在右侧编辑编码和名称。编码建议稳定，便于其他模块长期引用。")

        category_form = QFormLayout()
        configure_form_layout(category_form)
        category_form.addRow(build_form_label("一级编码"), self.category_code_input)
        category_form.addRow(build_form_label("一级名称"), self.category_name_input)
        editor_card.body_layout.addLayout(category_form)
        editor_card.body_layout.addWidget(apply_category_button)

        child_form = QFormLayout()
        configure_form_layout(child_form)
        child_form.addRow(build_form_label("二级编码"), self.child_code_input)
        child_form.addRow(build_form_label("二级名称"), self.child_name_input)
        editor_card.body_layout.addLayout(child_form)
        editor_card.body_layout.addWidget(apply_child_button)
        editor_card.body_layout.addWidget(save_button)
        editor_card.body_layout.addWidget(reload_button)

        tips_card = SectionCard("管理规则", "这套分类字典会被其他模块复用，因此保存前会做去重和空值校验。")
        tips_label = QLabel(
            "1. 一级分类代表业务域，例如交易中心、运营平台。\n"
            "2. 二级分类代表具体子域，例如下单、退款、活动配置。\n"
            "3. 下游模块默认优先选择叶子节点，避免归属粒度过粗。"
        )
        tips_label.setWordWrap(True)
        tips_card.body_layout.addWidget(tips_label)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(18)
        right_layout.addWidget(editor_card)
        right_layout.addWidget(tips_card)
        right_layout.addWidget(self.preview_view)

        page_splitter.addWidget(left_panel)
        page_splitter.addWidget(right_panel)
        page_splitter.setStretchFactor(0, 4)
        page_splitter.setStretchFactor(1, 5)

        layout.addWidget(page_splitter)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scaffold)

    def _load_categories(self) -> None:
        self.categories = self.controller.list_business_categories()
        self.selected_category_index = 0 if self.categories else None
        self.selected_child_index = None
        self._render_category_list()
        self._render_child_list()
        self._sync_editor_fields()
        self._refresh_preview()

    def _render_category_list(self) -> None:
        self.category_list.blockSignals(True)
        self.category_list.clear()
        for index, category in enumerate(self.categories):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, index)
            item.setSizeHint(self._build_category_item_widget(category, index == self.selected_category_index).sizeHint())
            self.category_list.addItem(item)
            self.category_list.setItemWidget(item, self._build_category_item_widget(category, index == self.selected_category_index))
        if self.selected_category_index is not None and 0 <= self.selected_category_index < self.category_list.count():
            self.category_list.setCurrentRow(self.selected_category_index)
        self.category_summary_label.setText(f"共 {len(self.categories)} 个一级分类")
        if not self.categories:
            empty_item = QListWidgetItem()
            empty_item.setFlags(Qt.NoItemFlags)
            empty_widget = self._build_empty_state_widget("当前没有一级分类，先点击“新增一级分类”。")
            empty_item.setSizeHint(empty_widget.sizeHint())
            self.category_list.addItem(empty_item)
            self.category_list.setItemWidget(empty_item, empty_widget)
        self.category_list.blockSignals(False)

    def _render_child_list(self) -> None:
        self.child_list.blockSignals(True)
        self.child_list.clear()
        category = self._current_category()
        if category is not None:
            for index, child in enumerate(category.children):
                item = QListWidgetItem()
                item.setData(Qt.UserRole, index)
                item.setSizeHint(
                    self._build_child_item_widget(
                        child,
                        parent_name=category.name,
                        is_selected=index == self.selected_child_index,
                    ).sizeHint()
                )
                self.child_list.addItem(item)
                self.child_list.setItemWidget(
                    item,
                    self._build_child_item_widget(
                        child,
                        parent_name=category.name,
                        is_selected=index == self.selected_child_index,
                    ),
                )
        if self.selected_child_index is not None and 0 <= self.selected_child_index < self.child_list.count():
            self.child_list.setCurrentRow(self.selected_child_index)
        if category is None:
            self.child_summary_label.setText("请先选择一个一级分类")
            empty_item = QListWidgetItem()
            empty_item.setFlags(Qt.NoItemFlags)
            empty_widget = self._build_empty_state_widget("选中左侧一级分类后，这里才会展示对应的二级分类。")
            empty_item.setSizeHint(empty_widget.sizeHint())
            self.child_list.addItem(empty_item)
            self.child_list.setItemWidget(empty_item, empty_widget)
        elif not category.children:
            self.child_summary_label.setText(f"{category.name} 下暂无二级分类")
            empty_item = QListWidgetItem()
            empty_item.setFlags(Qt.NoItemFlags)
            empty_widget = self._build_empty_state_widget("当前一级分类还没有二级分类，点击“新增二级分类”即可添加。")
            empty_item.setSizeHint(empty_widget.sizeHint())
            self.child_list.addItem(empty_item)
            self.child_list.setItemWidget(empty_item, empty_widget)
        else:
            self.child_summary_label.setText(f"{category.name} 下共 {len(category.children)} 个二级分类")
        self.child_list.blockSignals(False)

    def _sync_editor_fields(self) -> None:
        category = self._current_category()
        if category is None:
            self.category_code_input.clear()
            self.category_name_input.clear()
            self.child_code_input.clear()
            self.child_name_input.clear()
            return

        self.category_code_input.setText(category.code)
        self.category_name_input.setText(category.name)
        child = self._current_child()
        if child is None:
            self.child_code_input.clear()
            self.child_name_input.clear()
            return
        self.child_code_input.setText(child.code)
        self.child_name_input.setText(child.name)

    def _refresh_preview(self) -> None:
        options = self._build_option_payload()
        summary_lines = ["<h3>当前分类树</h3><ul>"]
        if not self.categories:
            summary_lines.append("<li>当前还没有业务分类。</li>")
        for category in self.categories:
            if not category.children:
                summary_lines.append(f"<li>{category.name}</li>")
                continue
            child_names = " / ".join(child.name for child in category.children)
            summary_lines.append(f"<li>{category.name}：{child_names}</li>")
        summary_lines.append("</ul>")
        self.preview_view.set_result(
            status="业务分类已加载",
            metrics=[
                (str(len(self.categories)), "一级分类"),
                (str(sum(len(item.children) for item in self.categories)), "二级分类"),
                (str(len(options)), "可选归属"),
            ],
            summary_html="".join(summary_lines),
            payload={
                "categories": [item.model_dump(mode="json") for item in self.categories],
                "options": options,
            },
        )

    def _handle_category_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self.selected_category_index = current.data(Qt.UserRole) if current is not None else None
        self.selected_child_index = None
        self._render_category_list()
        self._render_child_list()
        self._sync_editor_fields()

    def _handle_child_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self.selected_child_index = current.data(Qt.UserRole) if current is not None else None
        self._render_child_list()
        self._sync_editor_fields()

    def _add_category(self) -> None:
        next_index = len(self.categories) + 1
        self.categories.append(
            BusinessCategory(
                code=f"category_{next_index}",
                name=f"未命名一级分类{next_index}",
            )
        )
        self.selected_category_index = len(self.categories) - 1
        self.selected_child_index = None
        self._render_category_list()
        self._render_child_list()
        self._sync_editor_fields()
        self._refresh_preview()

    def _delete_category(self) -> None:
        category = self._current_category()
        if category is None:
            show_warning_dialog(self, title="无法删除", message="请先选择要删除的一级分类。")
            return
        confirmed = ask_confirmation(
            self,
            title="删除一级分类",
            message=f"删除后会同时移除“{category.name}”及其全部二级分类，是否继续？",
            confirm_text="确认删除",
        )
        if not confirmed:
            return
        assert self.selected_category_index is not None
        del self.categories[self.selected_category_index]
        if not self.categories:
            self.selected_category_index = None
        else:
            self.selected_category_index = min(self.selected_category_index, len(self.categories) - 1)
        self.selected_child_index = None
        self._render_category_list()
        self._render_child_list()
        self._sync_editor_fields()
        self._refresh_preview()

    def _add_child(self) -> None:
        category = self._current_category()
        if category is None:
            show_warning_dialog(self, title="无法新增", message="请先选择一个一级分类，再新增二级分类。")
            return
        next_index = len(category.children) + 1
        category.children.append(
            BusinessSubcategory(
                code=f"subcategory_{next_index}",
                name=f"未命名二级分类{next_index}",
            )
        )
        self.selected_child_index = len(category.children) - 1
        self._render_category_list()
        self._render_child_list()
        self._sync_editor_fields()
        self._refresh_preview()

    def _delete_child(self) -> None:
        category = self._current_category()
        child = self._current_child()
        if category is None or child is None or self.selected_child_index is None:
            show_warning_dialog(self, title="无法删除", message="请先选择要删除的二级分类。")
            return
        confirmed = ask_confirmation(
            self,
            title="删除二级分类",
            message=f"确认删除“{category.name} / {child.name}”吗？",
            confirm_text="确认删除",
        )
        if not confirmed:
            return
        del category.children[self.selected_child_index]
        if not category.children:
            self.selected_child_index = None
        else:
            self.selected_child_index = min(self.selected_child_index, len(category.children) - 1)
        self._render_category_list()
        self._render_child_list()
        self._sync_editor_fields()
        self._refresh_preview()

    def _apply_category_edit(self) -> None:
        category = self._current_category()
        if category is None:
            show_warning_dialog(self, title="无法应用", message="请先选择一个一级分类。")
            return
        code = self.category_code_input.text().strip()
        name = self.category_name_input.text().strip()
        if not code or not name:
            show_warning_dialog(self, title="信息不完整", message="一级分类的编码和名称不能为空。")
            return
        # 这里先更新页面内存态，统一在“保存全部变更”时做全量校验并落盘，避免半保存状态污染配置。
        category.code = code
        category.name = name
        self._render_category_list()
        self._sync_editor_fields()
        self._refresh_preview()

    def _apply_child_edit(self) -> None:
        child = self._current_child()
        if child is None:
            show_warning_dialog(self, title="无法应用", message="请先选择一个二级分类。")
            return
        code = self.child_code_input.text().strip()
        name = self.child_name_input.text().strip()
        if not code or not name:
            show_warning_dialog(self, title="信息不完整", message="二级分类的编码和名称不能为空。")
            return
        child.code = code
        child.name = name
        self._render_child_list()
        self._sync_editor_fields()
        self._refresh_preview()

    def _save_all(self) -> None:
        try:
            self._apply_pending_form_data()
            saved_categories = self.controller.save_business_categories(self.categories)
        except ValueError as exc:
            show_error_dialog(self, title="保存失败", message=str(exc))
            return
        self.categories = saved_categories
        self._render_category_list()
        self._render_child_list()
        self._sync_editor_fields()
        self._refresh_preview()
        show_info_dialog(self, title="保存成功", message="业务分类字典已更新。")

    def _apply_pending_form_data(self) -> None:
        category = self._current_category()
        if category is not None:
            category.code = self.category_code_input.text().strip()
            category.name = self.category_name_input.text().strip()
        child = self._current_child()
        if child is not None:
            child.code = self.child_code_input.text().strip()
            child.name = self.child_name_input.text().strip()

    def _current_category(self) -> BusinessCategory | None:
        if self.selected_category_index is None:
            return None
        if not 0 <= self.selected_category_index < len(self.categories):
            return None
        return self.categories[self.selected_category_index]

    def _current_child(self) -> BusinessSubcategory | None:
        category = self._current_category()
        if category is None or self.selected_child_index is None:
            return None
        if not 0 <= self.selected_child_index < len(category.children):
            return None
        return category.children[self.selected_child_index]

    def _build_option_payload(self) -> list[dict[str, str | None]]:
        options: list[dict[str, str | None]] = []
        for category in self.categories:
            if not category.children:
                options.append(
                    {
                        "value": category.code,
                        "label": category.name,
                        "level1_code": category.code,
                        "level1_name": category.name,
                        "level2_code": None,
                        "level2_name": None,
                    }
                )
                continue
            for child in category.children:
                options.append(
                    {
                        "value": f"{category.code}/{child.code}",
                        "label": f"{category.name} / {child.name}",
                        "level1_code": category.code,
                        "level1_name": category.name,
                        "level2_code": child.code,
                        "level2_name": child.name,
                    }
                )
        return options

    def _build_category_item_widget(self, category: BusinessCategory, is_selected: bool) -> QWidget:
        return self._build_list_card(
            title=category.name,
            badge_text=f"{len(category.children)} 个二级" if category.children else "待补子类",
            meta_lines=[
                f"编码：{category.code}",
                "层级：一级业务域",
            ],
            is_selected=is_selected,
        )

    def _build_child_item_widget(
        self,
        child: BusinessSubcategory,
        *,
        parent_name: str,
        is_selected: bool,
    ) -> QWidget:
        return self._build_list_card(
            title=child.name,
            badge_text="叶子节点",
            meta_lines=[
                f"编码：{child.code}",
                f"归属：{parent_name}",
            ],
            is_selected=is_selected,
        )

    def _build_list_card(
        self,
        *,
        title: str,
        badge_text: str,
        meta_lines: list[str],
        is_selected: bool,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("businessCategoryListItem")
        card.setProperty("selected", is_selected)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("businessCategoryListTitle")
        title_label.setWordWrap(True)

        badge_shell = QFrame()
        badge_shell.setObjectName("businessCategoryListBadgeShell")
        badge_shell.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        badge_shell.setMinimumHeight(30)
        badge_layout = QHBoxLayout(badge_shell)
        badge_layout.setContentsMargins(12, 6, 12, 6)
        badge_layout.setSpacing(0)

        badge = QLabel(badge_text)
        badge.setObjectName("businessCategoryListBadgeText")
        badge.setAlignment(Qt.AlignCenter)
        badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        badge.setMinimumHeight(18)
        badge_layout.addWidget(badge)

        header.addWidget(title_label, 1)
        header.addWidget(badge_shell, 0, Qt.AlignTop)
        layout.addLayout(header)

        for line in meta_lines:
            meta_label = QLabel(line)
            meta_label.setObjectName("businessCategoryListMeta")
            meta_label.setWordWrap(True)
            layout.addWidget(meta_label)

        return card

    def _build_empty_state_widget(self, message: str) -> QWidget:
        shell = QFrame()
        shell.setObjectName("businessCategoryEmptyState")
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title = QLabel("暂无内容")
        title.setObjectName("businessCategoryEmptyTitle")
        detail = QLabel(message)
        detail.setObjectName("businessCategoryEmptyText")
        detail.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(detail)
        return shell
