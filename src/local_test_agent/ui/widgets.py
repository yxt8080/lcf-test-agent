from __future__ import annotations

import json
from time import monotonic
from typing import Any, Callable, Sequence, TypeVar

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
    QTextBrowser,
    QVBoxLayout,
)

ResultT = TypeVar("ResultT")


class SectionCard(QFrame):
    """统一的卡片容器，保证所有页面具备一致的视觉层级。"""

    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        self.setObjectName("sectionCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 22, 24, 24)
        self._layout.setSpacing(18)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        self._layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("sectionDescription")
            desc_label.setWordWrap(True)
            self._layout.addWidget(desc_label)

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._layout


class PageScaffold(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: str,
        *,
        eyebrow: str = "LOCAL TEST AGENT",
        meta: str = "单机工作台",
    ) -> None:
        super().__init__()
        self.setObjectName("pageScaffold")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("pageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.viewport().setObjectName("pageViewport")
        root_layout.addWidget(scroll_area)

        page_surface = QFrame()
        page_surface.setObjectName("pageSurface")
        scroll_area.setWidget(page_surface)

        self.content_layout = QVBoxLayout(page_surface)
        self.content_layout.setContentsMargins(32, 28, 32, 32)
        self.content_layout.setSpacing(24)

        self.content_layout.addWidget(build_hero_banner(title, subtitle, eyebrow=eyebrow, meta=meta))


def build_hero_banner(title: str, subtitle: str, *, eyebrow: str, meta: str) -> QFrame:
    banner = QFrame()
    banner.setObjectName("heroBanner")
    layout = QVBoxLayout(banner)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(10)

    eyebrow_label = QLabel(eyebrow)
    eyebrow_label.setObjectName("heroEyebrow")
    title_label = QLabel(title)
    title_label.setObjectName("heroTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("heroSubtitle")
    subtitle_label.setWordWrap(True)
    meta_label = QLabel(meta)
    meta_label.setObjectName("heroMeta")
    meta_label.setAlignment(Qt.AlignCenter)
    meta_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    top_row = QHBoxLayout()
    top_row.addWidget(eyebrow_label)
    top_row.addStretch(1)
    top_row.addWidget(meta_label)

    layout.addLayout(top_row)
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return banner


def _polish_widget(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _build_button(text: str, role: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("role", role)
    button.setProperty("interactionState", "idle")
    button.setCursor(Qt.PointingHandCursor)
    # 统一按钮基础尺寸，避免主题放大后出现过高的“桌面表单块”观感。
    button.setMinimumHeight(40)
    button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
    _polish_widget(button)
    return button


def build_primary_button(text: str) -> QPushButton:
    return _build_button(text, "primary")


def build_secondary_button(text: str) -> QPushButton:
    return _build_button(text, "secondary")


def build_danger_button(text: str) -> QPushButton:
    return _build_button(text, "danger")


class CollapsibleSection(QFrame):
    """默认折叠的辅助信息区。

    需求分析页里的建议说明、待确认项都属于“按需查看”的信息，
    用统一折叠组件收敛后，可以明显降低首屏信息密度。
    """

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        expanded: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName("collapsibleSection")
        self._expanded = expanded
        self._body = QFrame()
        self._body.setObjectName("collapsibleSectionBody")
        self._build_ui(title, description)
        self.set_expanded(expanded)

    def _build_ui(self, title: str, description: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName("collapsibleToggle")
        self.toggle_button.setProperty("role", "disclosure")
        self.toggle_button.setCheckable(True)
        self.toggle_button.clicked.connect(self._handle_toggle_clicked)
        layout.addWidget(self.toggle_button)

        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(16, 14, 16, 16)
        self._body_layout.setSpacing(12)
        layout.addWidget(self._body)

        self._title = title
        self._description = description
        self._refresh_toggle_text()

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.toggle_button.blockSignals(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.blockSignals(False)
        self._body.setVisible(expanded)
        self._refresh_toggle_text()

    def _handle_toggle_clicked(self, checked: bool) -> None:
        self.set_expanded(checked)

    def _refresh_toggle_text(self) -> None:
        arrow = "▾" if self._expanded else "▸"
        suffix = f"  {self._description}" if self._description else ""
        self.toggle_button.setText(f"{arrow}  {self._title}{suffix}")
        _polish_widget(self.toggle_button)


class ButtonBusyState:
    """统一管理按钮忙碌态。

    这里把“按钮文案变化 + 禁用重复点击 + 样式刷新”收敛到一个小对象里，
    避免每个页面都手动拼接同样的交互细节，后续新增按钮也能直接复用。
    """

    def __init__(
        self,
        button: QPushButton,
        *,
        busy_text: str,
        disable_widgets: Sequence[QWidget] | None = None,
    ) -> None:
        self.button = button
        self.busy_text = busy_text
        self._idle_text = button.text()
        self._widget_states: list[tuple[QWidget, bool]] = []
        self._active = False

        widgets: list[QWidget] = [button]
        if disable_widgets:
            for widget in disable_widgets:
                if widget not in widgets:
                    widgets.append(widget)
        self._managed_widgets = widgets

    def start(self) -> None:
        if self._active:
            return

        self._active = True
        self._idle_text = self.button.text()
        self._widget_states = [(widget, widget.isEnabled()) for widget in self._managed_widgets]
        for widget, _was_enabled in self._widget_states:
            widget.setEnabled(False)
            if isinstance(widget, QPushButton):
                widget.setCursor(Qt.ArrowCursor)

        self.button.setText(self.busy_text)
        self.button.setProperty("interactionState", "busy")
        self.button.setCursor(Qt.BusyCursor)
        _polish_widget(self.button)

    def finish(self) -> None:
        if not self._active:
            return

        self._active = False
        self.button.setText(self._idle_text)
        self.button.setProperty("interactionState", "idle")
        for widget, was_enabled in self._widget_states:
            widget.setEnabled(was_enabled)
            if isinstance(widget, QPushButton):
                widget.setCursor(Qt.PointingHandCursor if was_enabled else Qt.ArrowCursor)
        self._widget_states = []
        _polish_widget(self.button)


def begin_async_button_feedback(
    button: QPushButton,
    *,
    busy_text: str,
    on_success: Callable[[ResultT], None],
    on_error: Callable[[str], None],
    disable_widgets: Sequence[QWidget] | None = None,
) -> tuple[Callable[[ResultT], None], Callable[[str], None]]:
    """包装异步回调，统一提供按钮忙碌态反馈。"""

    feedback = ButtonBusyState(
        button,
        busy_text=busy_text,
        disable_widgets=disable_widgets,
    )
    feedback.start()

    def handle_success(result: ResultT) -> None:
        feedback.finish()
        on_success(result)

    def handle_error(message: str) -> None:
        feedback.finish()
        on_error(message)

    return handle_success, handle_error


def build_form_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("formLabel")
    return label


def configure_form_layout(form: QFormLayout) -> None:
    """统一表单布局策略，避免输入控件被系统默认样式压成窄宽度。"""

    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(18)
    form.setVerticalSpacing(16)
    form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
    form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)


def configure_line_input(widget: QWidget, *, min_width: int = 420, min_height: int = 54) -> None:
    widget.setMinimumWidth(min_width)
    widget.setMinimumHeight(min_height)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class AppSelect(QWidget):
    """项目内统一选择器。

    原生 QComboBox 在 macOS 下会混入系统 popup 容器，视觉上容易出现黑色外框。
    这里改成项目自绘 trigger + 自定义 popup，后续所有下拉统一复用这一套。
    """

    currentIndexChanged = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._items: list[tuple[str, object]] = []
        self._current_index = -1
        self._max_visible_items = 10
        self._popup: QFrame | None = None
        self._list_widget: QListWidget | None = None
        self.setObjectName("appSelect")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()
        self._apply_local_styles()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.trigger_button = QPushButton()
        self.trigger_button.setObjectName("appSelectTrigger")
        self.trigger_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.trigger_button.clicked.connect(self._toggle_popup)

        trigger_layout = QHBoxLayout(self.trigger_button)
        trigger_layout.setContentsMargins(14, 0, 14, 0)
        trigger_layout.setSpacing(10)

        self.value_label = QLabel("")
        self.value_label.setObjectName("appSelectValue")
        self.value_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.arrow_label = QLabel("▾")
        self.arrow_label.setObjectName("appSelectArrow")
        self.arrow_label.setAlignment(Qt.AlignCenter)
        self.arrow_label.setFixedWidth(18)

        trigger_layout.addWidget(self.value_label, 1)
        trigger_layout.addWidget(self.arrow_label)
        layout.addWidget(self.trigger_button)
        self._refresh_display()

    def _apply_local_styles(self) -> None:
        # 顶层 popup 在 macOS 下容易回退到系统深色面板，这里直接把选择器本体和弹层样式收敛到组件内部。
        self.setStyleSheet(
            """
            QWidget#appSelect {
                background: transparent;
            }

            QPushButton#appSelectTrigger {
                background: #fffdfa;
                color: #173042;
                border: 1px solid #d8ccb8;
                border-radius: 14px;
                padding: 0;
                text-align: left;
                font-size: 13px;
                font-weight: 600;
                min-height: 52px;
            }

            QPushButton#appSelectTrigger:hover {
                background: #fff7ec;
                border: 1px solid #cfbea2;
            }

            QPushButton#appSelectTrigger:pressed {
                background: #f6ecdc;
            }

            QPushButton#appSelectTrigger:disabled {
                background: #f6f1e8;
                color: #8b96a1;
                border: 1px solid #ddd2c0;
            }

            QLabel#appSelectValue {
                color: #173042;
                font-size: 13px;
                font-weight: 600;
            }

            QLabel#appSelectValue[placeholder="true"] {
                color: #7d8996;
            }

            QLabel#appSelectArrow {
                color: #6b7b88;
                font-size: 12px;
                font-weight: 700;
            }
            """
        )

    @staticmethod
    def _popup_stylesheet() -> str:
        return """
        QFrame#appSelectPopup {
            background: #fffaf3;
            border: 1px solid #d8ccb8;
            border-radius: 14px;
        }

        QListWidget#appSelectList {
            background: transparent;
            color: #173042;
            border: none;
            border-radius: 12px;
            padding: 6px;
            outline: 0;
            font-size: 13px;
            font-weight: 600;
        }

        QListWidget#appSelectList::item {
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 10px 12px;
            margin: 2px 0;
            min-height: 18px;
            background: transparent;
        }

        QListWidget#appSelectList::item:hover {
            background: #f4ebdc;
            border: 1px solid #e4d4b9;
        }

        QListWidget#appSelectList::item:selected {
            background: #dff0ec;
            color: #12414b;
            border: 1px solid #9dc9c0;
        }

        QListWidget#appSelectList::item:selected:active,
        QListWidget#appSelectList::item:selected:!active {
            background: #dff0ec;
            color: #12414b;
            border: 1px solid #9dc9c0;
        }

        QListWidget#appSelectList QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 8px 2px 8px 0;
        }

        QListWidget#appSelectList QScrollBar::handle:vertical {
            background: #d4c4aa;
            border-radius: 5px;
            min-height: 28px;
        }

        QListWidget#appSelectList QScrollBar::add-line:vertical,
        QListWidget#appSelectList QScrollBar::sub-line:vertical,
        QListWidget#appSelectList QScrollBar::add-page:vertical,
        QListWidget#appSelectList QScrollBar::sub-page:vertical {
            background: transparent;
            border: none;
            height: 0;
        }
        """

    def addItem(self, text: str, user_data: object = None) -> None:
        self._items.append((text, text if user_data is None else user_data))
        if self._current_index == -1:
            self.setCurrentIndex(0)
        else:
            self._refresh_popup_items()

    def addItems(self, texts: list[str]) -> None:
        for text in texts:
            self.addItem(text, text)

    def clear(self) -> None:
        self._items = []
        self._current_index = -1
        self._refresh_display()
        self._refresh_popup_items()

    def count(self) -> int:
        return len(self._items)

    def itemData(self, index: int, role: int = Qt.UserRole) -> object:
        if role != Qt.UserRole or not 0 <= index < len(self._items):
            return None
        return self._items[index][1]

    def currentData(self, role: int = Qt.UserRole) -> object:
        return self.itemData(self._current_index, role)

    def currentText(self) -> str:
        if not 0 <= self._current_index < len(self._items):
            return ""
        return self._items[self._current_index][0]

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < len(self._items):
            index = -1
        if self._current_index == index:
            self._refresh_display()
            self._refresh_popup_selection()
            return
        self._current_index = index
        self._refresh_display()
        self._refresh_popup_selection()
        self.currentIndexChanged.emit(index)

    def currentIndex(self) -> int:
        return self._current_index

    def setMaxVisibleItems(self, count: int) -> None:
        self._max_visible_items = max(1, count)

    def popupWidget(self) -> QFrame:
        if self._popup is None:
            popup = QFrame(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            popup.setObjectName("appSelectPopup")
            popup.setAttribute(Qt.WA_StyledBackground, True)
            popup.setStyleSheet(self._popup_stylesheet())
            popup_layout = QVBoxLayout(popup)
            popup_layout.setContentsMargins(0, 0, 0, 0)
            popup_layout.setSpacing(0)

            list_widget = QListWidget()
            list_widget.setObjectName("appSelectList")
            list_widget.setFrameShape(QFrame.NoFrame)
            list_widget.setSpacing(2)
            list_widget.itemClicked.connect(self._handle_item_clicked)
            popup_layout.addWidget(list_widget)

            self._popup = popup
            self._list_widget = list_widget
            self._refresh_popup_items()
        return self._popup

    def _toggle_popup(self) -> None:
        if not self.isEnabled():
            return
        popup = self.popupWidget()
        if popup.isVisible():
            popup.hide()
            return
        self._refresh_popup_items()
        self._refresh_popup_selection()
        popup_width = max(self.width(), 260)
        row_count = min(max(self.count(), 1), self._max_visible_items)
        row_height = 40
        if self._list_widget is not None:
            hinted = self._list_widget.sizeHintForRow(0)
            if hinted > 0:
                row_height = max(36, hinted)
            list_height = row_count * row_height + 12
            self._list_widget.setFixedHeight(list_height)
            popup_height = list_height + 2
        else:
            popup_height = row_count * row_height + 14
        popup.resize(popup_width, popup_height)
        popup.move(self.mapToGlobal(QPoint(0, self.height() + 6)))
        popup.show()
        popup.raise_()

    def _refresh_display(self) -> None:
        current_text = self.currentText()
        self.value_label.setText(current_text)
        self.value_label.setProperty("placeholder", str(not bool(current_text)).lower())
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)

    def _refresh_popup_items(self) -> None:
        if self._list_widget is None:
            return
        self._list_widget.clear()
        for index, (text, user_data) in enumerate(self._items):
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, user_data)
            item.setData(Qt.UserRole + 1, index)
            self._list_widget.addItem(item)

    def _refresh_popup_selection(self) -> None:
        if self._list_widget is None:
            return
        self._list_widget.blockSignals(True)
        self._list_widget.setCurrentRow(self._current_index)
        self._list_widget.blockSignals(False)

    def _handle_item_clicked(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.UserRole + 1)
        self.setCurrentIndex(index)
        if self._popup is not None:
            self._popup.hide()


def configure_combo_input(widget: QWidget, *, min_width: int = 420, min_height: int = 54) -> None:
    configure_line_input(widget, min_width=min_width, min_height=min_height)
    if isinstance(widget, AppSelect):
        widget.setMaxVisibleItems(10)


def configure_text_input(widget: QWidget, *, min_width: int = 520, min_height: int = 280) -> None:
    widget.setMinimumWidth(min_width)
    widget.setMinimumHeight(min_height)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


def configure_expanding_container(widget: QWidget, *, min_width: int = 520, min_height: int = 54) -> None:
    widget.setMinimumWidth(min_width)
    widget.setMinimumHeight(min_height)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class AppMessageDialog(QDialog):
    """统一消息对话框。

    项目内所有提醒、告警、错误和确认弹窗都应走这里，
    避免继续散落使用系统原生 QMessageBox，导致样式与交互割裂。
    """

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        message: str,
        tone: str = "info",
        confirm_text: str = "我知道了",
        cancel_text: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("appMessageDialog")
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        shell = QFrame()
        shell.setObjectName("dialogShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(24, 22, 24, 22)
        shell_layout.setSpacing(18)

        eyebrow_label = QLabel(self._tone_label(tone))
        eyebrow_label.setObjectName("dialogEyebrow")
        eyebrow_label.setProperty("tone", tone)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        message_label = QLabel(message)
        message_label.setObjectName("dialogMessage")
        message_label.setWordWrap(True)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(10)
        action_layout.addStretch(1)

        if cancel_text:
            cancel_button = build_secondary_button(cancel_text)
            cancel_button.clicked.connect(self.reject)
            action_layout.addWidget(cancel_button)

        confirm_button = self._build_confirm_button(tone, confirm_text)
        confirm_button.clicked.connect(self.accept)
        action_layout.addWidget(confirm_button)

        shell_layout.addWidget(eyebrow_label)
        shell_layout.addWidget(title_label)
        shell_layout.addWidget(message_label)
        shell_layout.addLayout(action_layout)
        layout.addWidget(shell)

    @staticmethod
    def _tone_label(tone: str) -> str:
        labels = {
            "info": "信息提醒",
            "warning": "操作提醒",
            "error": "错误提示",
            "danger": "高风险操作",
        }
        return labels.get(tone, "信息提醒")

    @staticmethod
    def _build_confirm_button(tone: str, text: str) -> QPushButton:
        if tone == "danger":
            return build_danger_button(text)
        return build_primary_button(text)


def ask_confirmation(
    parent: QWidget | None,
    *,
    title: str,
    message: str,
    confirm_text: str = "确认",
    cancel_text: str = "取消",
) -> bool:
    dialog = AppMessageDialog(
        parent,
        title=title,
        message=message,
        tone="danger",
        confirm_text=confirm_text,
        cancel_text=cancel_text,
    )
    return dialog.exec() == QDialog.Accepted


def show_info_dialog(
    parent: QWidget | None,
    *,
    title: str,
    message: str,
    confirm_text: str = "好的",
) -> None:
    dialog = AppMessageDialog(
        parent,
        title=title,
        message=message,
        tone="info",
        confirm_text=confirm_text,
    )
    dialog.exec()


def show_warning_dialog(
    parent: QWidget | None,
    *,
    title: str,
    message: str,
    confirm_text: str = "我知道了",
) -> None:
    dialog = AppMessageDialog(
        parent,
        title=title,
        message=message,
        tone="warning",
        confirm_text=confirm_text,
    )
    dialog.exec()


def show_error_dialog(
    parent: QWidget | None,
    *,
    title: str,
    message: str,
    confirm_text: str = "关闭",
) -> None:
    dialog = AppMessageDialog(
        parent,
        title=title,
        message=message,
        tone="error",
        confirm_text=confirm_text,
    )
    dialog.exec()


class StructuredTable(QWidget):
    """轻量结构化表格。

    使用普通布局模拟表格，避免原生表头、角落按钮和 viewport 在桌面端样式叠层下出现割裂感。
    """

    def __init__(self, columns: list[tuple[str, int]]) -> None:
        super().__init__()
        self.columns = columns
        self.body_layout: QVBoxLayout | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("structuredTableShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(1, 1, 1, 1)
        shell_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("structuredTableHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        for index, (title, stretch) in enumerate(self.columns):
            header_layout.addWidget(
                self._build_header_cell(title, is_last_col=index == len(self.columns) - 1),
                stretch,
            )
            if index < len(self.columns) - 1:
                header_layout.addWidget(self._build_divider("structuredTableHeaderDivider"))
        shell_layout.addWidget(header)
        shell_layout.addWidget(self._build_horizontal_divider("structuredTableHeaderSeparator"))

        body = QWidget()
        body.setObjectName("structuredTableBody")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        shell_layout.addWidget(body)

        root_layout.addWidget(shell)

    def clear_rows(self) -> None:
        assert self.body_layout is not None
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_row(self, cells: list[QWidget | str], *, is_last_row: bool = False) -> None:
        assert self.body_layout is not None
        row = QFrame()
        row.setObjectName("structuredTableRow")
        row.setProperty("lastRow", is_last_row)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        for index, ((title, stretch), cell) in enumerate(zip(self.columns, cells, strict=True)):
            _ = title
            row_layout.addWidget(
                self._build_body_cell(
                    cell,
                    is_first_col=index == 0,
                    is_last_col=index == len(self.columns) - 1,
                    is_last_row=is_last_row,
                ),
                stretch,
            )
            if index < len(self.columns) - 1:
                row_layout.addWidget(self._build_divider("structuredTableBodyDivider"))
        self.body_layout.addWidget(row)
        if not is_last_row:
            self.body_layout.addWidget(self._build_horizontal_divider("structuredTableRowSeparator"))

    @staticmethod
    def _build_header_cell(title: str, *, is_last_col: bool) -> QWidget:
        cell = QFrame()
        cell.setObjectName("structuredTableHeaderCell")
        cell.setProperty("lastCol", is_last_col)
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(0)
        label = QLabel(title)
        label.setObjectName("structuredTableHeaderText")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(label)
        return cell

    @staticmethod
    def _build_body_cell(
        content: QWidget | str,
        *,
        is_first_col: bool,
        is_last_col: bool,
        is_last_row: bool,
    ) -> QWidget:
        cell = QFrame()
        cell.setObjectName("structuredTableCell")
        cell.setProperty("firstCol", is_first_col)
        cell.setProperty("lastCol", is_last_col)
        cell.setProperty("lastRow", is_last_row)
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(0)
        if isinstance(content, str):
            label = QLabel(content)
            label.setObjectName("structuredTableCellText")
            label.setWordWrap(True)
            layout.addWidget(label)
        else:
            layout.addWidget(content)
        return cell

    @staticmethod
    def _build_divider(object_name: str) -> QWidget:
        divider = QFrame()
        divider.setObjectName(object_name)
        divider.setFixedWidth(1)
        return divider

    @staticmethod
    def _build_horizontal_divider(object_name: str) -> QWidget:
        divider = QFrame()
        divider.setObjectName(object_name)
        divider.setFixedHeight(1)
        return divider


class ScenarioHandoffList(QWidget):
    """场景交接列表。

    这里的核心诉求是“阅读场景信息并快速选择去向”，并不是做传统数据表检索，
    因此用卡片式列表替代表格，减少样式不稳定和视觉割裂。
    """

    def __init__(self) -> None:
        super().__init__()
        self.body_layout: QVBoxLayout | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.body_layout = layout

    def clear_rows(self) -> None:
        assert self.body_layout is not None
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_row(
        self,
        *,
        scenario_id: str,
        title: str,
        detail: str,
        priority: str,
        summary: str,
        step_preview: list[str],
        assertion_preview: list[str],
        actions: QWidget,
    ) -> None:
        assert self.body_layout is not None
        row = QFrame()
        row.setObjectName("scenarioHandoffRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(18, 16, 18, 16)
        row_layout.setSpacing(18)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        scenario_id_label = QLabel(scenario_id)
        scenario_id_label.setObjectName("scenarioHandoffId")
        scenario_id_label.setAlignment(Qt.AlignCenter)
        scenario_id_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        priority_label = QLabel(priority)
        priority_label.setObjectName("scenarioPriorityBadge")
        priority_label.setProperty("priority", priority)
        priority_label.setAlignment(Qt.AlignCenter)
        priority_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        title_label = QLabel(title)
        title_label.setObjectName("scenarioHandoffTitle")
        title_label.setWordWrap(True)

        detail_label = QLabel(detail)
        detail_label.setObjectName("scenarioHandoffMeta")
        detail_label.setWordWrap(True)

        summary_label = QLabel(summary)
        summary_label.setObjectName("scenarioHandoffSummary")
        summary_label.setWordWrap(True)

        step_text = " · ".join(step_preview) if step_preview else "无核心步骤预览"
        step_label = QLabel(f"步骤预览：{step_text}")
        step_label.setObjectName("scenarioHandoffPreview")
        step_label.setWordWrap(True)

        assertion_text = " · ".join(assertion_preview) if assertion_preview else "无关键断言预览"
        assertion_label = QLabel(f"关键断言：{assertion_text}")
        assertion_label.setObjectName("scenarioHandoffPreview")
        assertion_label.setWordWrap(True)

        header_row.addWidget(scenario_id_label, 0, Qt.AlignLeft)
        header_row.addWidget(priority_label, 0, Qt.AlignLeft)
        header_row.addStretch(1)

        content_layout.addLayout(header_row)
        content_layout.addWidget(title_label)
        content_layout.addWidget(detail_label)
        content_layout.addWidget(summary_label)
        content_layout.addWidget(step_label)
        content_layout.addWidget(assertion_label)

        action_wrap = QWidget()
        action_wrap.setObjectName("scenarioHandoffActionWrap")
        action_wrap.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        action_layout = QVBoxLayout(action_wrap)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(0)
        action_layout.addWidget(actions, 0, Qt.AlignTop | Qt.AlignRight)

        row_layout.addWidget(content, 1)
        row_layout.addWidget(action_wrap, 0, Qt.AlignRight | Qt.AlignTop)

        self.body_layout.addWidget(row)


class StructuredResultView(QWidget):
    """统一结果视图。

    默认只展示人可读摘要，原始 JSON 按需展开，避免结果区长期被大段结构化数据占满。
    """

    def __init__(self, placeholder: str) -> None:
        super().__init__()
        self.placeholder = placeholder
        self.metric_layout: QHBoxLayout | None = None
        self.status_label: QLabel | None = None
        self.status_feedback_wrap: QWidget | None = None
        self.status_indicator_label: QLabel | None = None
        self.status_meta_label: QLabel | None = None
        self.summary_browser: QTextBrowser | None = None
        self.raw_toggle_button: QPushButton | None = None
        self.raw_output: QPlainTextEdit | None = None
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(300)
        self._loading_timer.timeout.connect(self._refresh_loading_feedback)
        self._loading_started_at: float | None = None
        self._loading_frame_index = 0
        self._build_ui()
        self.set_placeholder()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.status_label = QLabel()
        self.status_label.setObjectName("resultStatus")
        layout.addWidget(self.status_label)

        self.status_feedback_wrap = QWidget()
        self.status_feedback_wrap.setObjectName("resultStatusFeedbackWrap")
        status_feedback_layout = QHBoxLayout(self.status_feedback_wrap)
        status_feedback_layout.setContentsMargins(0, 0, 0, 0)
        status_feedback_layout.setSpacing(8)

        self.status_indicator_label = QLabel()
        self.status_indicator_label.setObjectName("resultLoadingIndicator")
        self.status_indicator_label.setVisible(False)
        status_feedback_layout.addWidget(self.status_indicator_label, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self.status_meta_label = QLabel()
        self.status_meta_label.setObjectName("resultStatusMeta")
        status_feedback_layout.addWidget(self.status_meta_label, 0, Qt.AlignLeft | Qt.AlignVCenter)
        status_feedback_layout.addStretch(1)

        self.status_feedback_wrap.setVisible(False)
        layout.addWidget(self.status_feedback_wrap)

        metric_container = QWidget()
        self.metric_layout = QHBoxLayout(metric_container)
        self.metric_layout.setContentsMargins(0, 0, 0, 0)
        self.metric_layout.setSpacing(12)
        layout.addWidget(metric_container)

        self.summary_browser = QTextBrowser()
        self.summary_browser.setOpenExternalLinks(False)
        self.summary_browser.setMinimumHeight(240)
        layout.addWidget(self.summary_browser)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(10)
        toggle_label = QLabel("原始 JSON")
        toggle_label.setObjectName("sectionDescription")
        self.raw_toggle_button = build_secondary_button("展开")
        self.raw_toggle_button.setCheckable(True)
        self.raw_toggle_button.setEnabled(False)
        self.raw_toggle_button.toggled.connect(self._toggle_raw_output)
        toggle_row.addWidget(toggle_label)
        toggle_row.addStretch(1)
        toggle_row.addWidget(self.raw_toggle_button)
        layout.addLayout(toggle_row)

        self.raw_output = QPlainTextEdit()
        self.raw_output.setReadOnly(True)
        self.raw_output.setMinimumHeight(220)
        self.raw_output.setVisible(False)
        layout.addWidget(self.raw_output)

    def set_placeholder(self) -> None:
        self._clear_loading_feedback()
        self.set_result(
            status="等待结果",
            metrics=[],
            summary_html=f"<p>{self.placeholder}</p>",
            payload=None,
            finalize_loading_feedback=False,
        )

    def set_loading(self, text: str, *, show_thinking_feedback: bool = False) -> None:
        self._clear_loading_feedback()
        self.set_result(
            status=text,
            metrics=[],
            summary_html=f"<p>{text}</p>",
            payload=None,
            finalize_loading_feedback=False,
        )
        if show_thinking_feedback:
            self._start_loading_feedback()

    def set_result(
        self,
        *,
        status: str,
        metrics: list[tuple[str, str]],
        summary_html: str,
        payload: object | None,
        finalize_loading_feedback: bool = True,
    ) -> None:
        assert self.metric_layout is not None
        assert self.status_label is not None
        assert self.status_feedback_wrap is not None
        assert self.status_indicator_label is not None
        assert self.status_meta_label is not None
        assert self.summary_browser is not None
        assert self.raw_toggle_button is not None
        assert self.raw_output is not None

        elapsed_seconds = self._finish_loading_feedback() if finalize_loading_feedback else None
        self.status_label.setText(status)
        self._reset_metrics()
        for value, label in metrics:
            self.metric_layout.addWidget(self._build_metric_card(value, label))
        self.metric_layout.addStretch(1)

        if elapsed_seconds is None:
            self.status_indicator_label.clear()
            self.status_indicator_label.setVisible(False)
            self.status_meta_label.clear()
            self.status_meta_label.setVisible(False)
            self.status_feedback_wrap.setVisible(False)
        else:
            self.status_indicator_label.clear()
            self.status_indicator_label.setVisible(False)
            self.status_meta_label.setText(f"本次大模型调用耗时 {elapsed_seconds:.1f}s")
            self.status_meta_label.setVisible(True)
            self.status_feedback_wrap.setVisible(True)

        self.summary_browser.setHtml(summary_html)
        if payload is None:
            self.raw_output.setPlainText("")
            self.raw_output.setVisible(False)
            self.raw_toggle_button.setChecked(False)
            self.raw_toggle_button.setEnabled(False)
            self.raw_toggle_button.setText("展开")
        else:
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump(mode="json")
            self.raw_output.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
            self.raw_toggle_button.setEnabled(True)

    def _start_loading_feedback(self) -> None:
        assert self.status_feedback_wrap is not None
        assert self.status_indicator_label is not None
        assert self.status_meta_label is not None
        # 这里只统计前端实际等待大模型返回的耗时，便于用户判断当前调用是否异常偏慢。
        self._loading_started_at = monotonic()
        self._loading_frame_index = 0
        self.status_feedback_wrap.setVisible(True)
        self.status_indicator_label.setVisible(True)
        self.status_meta_label.setVisible(True)
        self._refresh_loading_feedback()
        self._loading_timer.start()

    def _clear_loading_feedback(self) -> None:
        assert self.status_feedback_wrap is not None
        assert self.status_indicator_label is not None
        assert self.status_meta_label is not None
        self._loading_timer.stop()
        self._loading_started_at = None
        self._loading_frame_index = 0
        self.status_indicator_label.clear()
        self.status_indicator_label.setVisible(False)
        self.status_meta_label.clear()
        self.status_meta_label.setVisible(False)
        self.status_feedback_wrap.setVisible(False)

    def _finish_loading_feedback(self) -> float | None:
        if self._loading_started_at is None:
            return None
        elapsed_seconds = max(0.0, monotonic() - self._loading_started_at)
        self._loading_timer.stop()
        self._loading_started_at = None
        self._loading_frame_index = 0
        return elapsed_seconds

    def _refresh_loading_feedback(self) -> None:
        assert self.status_feedback_wrap is not None
        assert self.status_indicator_label is not None
        assert self.status_meta_label is not None
        if self._loading_started_at is None:
            return
        frames = ["● ○ ○", "○ ● ○", "○ ○ ●"]
        indicator = frames[self._loading_frame_index % len(frames)]
        self._loading_frame_index += 1
        elapsed_seconds = max(0.0, monotonic() - self._loading_started_at)
        self.status_feedback_wrap.setVisible(True)
        self.status_indicator_label.setText(indicator)
        self.status_indicator_label.setVisible(True)
        self.status_meta_label.setText(f"思考中  已耗时 {elapsed_seconds:.1f}s")
        self.status_meta_label.setVisible(True)

    def _toggle_raw_output(self, checked: bool) -> None:
        assert self.raw_output is not None
        assert self.raw_toggle_button is not None
        self.raw_output.setVisible(checked)
        self.raw_toggle_button.setText("收起" if checked else "展开")

    def _reset_metrics(self) -> None:
        assert self.metric_layout is not None
        while self.metric_layout.count():
            item = self.metric_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_metric_card(self, value: str, label: str) -> QFrame:
        card = QFrame()
        card.setObjectName("resultMetricCard")
        card.setMinimumWidth(120)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setObjectName("resultMetricValue")
        text_label = QLabel(label)
        text_label.setObjectName("resultMetricLabel")
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)
        return card
