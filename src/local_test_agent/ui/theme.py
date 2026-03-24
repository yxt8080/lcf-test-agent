from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette


def build_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f3ede3"))
    palette.setColor(QPalette.WindowText, QColor("#1d2939"))
    palette.setColor(QPalette.Base, QColor("#fffdf8"))
    palette.setColor(QPalette.AlternateBase, QColor("#efe7d8"))
    palette.setColor(QPalette.ToolTipBase, QColor("#fffdf8"))
    palette.setColor(QPalette.ToolTipText, QColor("#1d2939"))
    palette.setColor(QPalette.Text, QColor("#1d2939"))
    palette.setColor(QPalette.Button, QColor("#fff9ef"))
    palette.setColor(QPalette.ButtonText, QColor("#1d2939"))
    palette.setColor(QPalette.Highlight, QColor("#0f766e"))
    palette.setColor(QPalette.HighlightedText, QColor("#f8fffd"))
    return palette


def build_font() -> QFont:
    font = QFont("PingFang SC")
    font.setPointSize(11)
    return font


def build_stylesheet() -> str:
    return """
    QMainWindow {
        background: #efe7d8;
    }

    QWidget {
        color: #1d2939;
        font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei';
    }

    QStatusBar {
        background: #e3d9c8;
        color: #526071;
        border-top: 1px solid #d6c7b2;
    }

    QFrame#mainShell {
        background: #efe7d8;
    }

    QFrame#sideRail {
        background: qlineargradient(
            x1: 0, y1: 0, x2: 0, y2: 1,
            stop: 0 #18344b,
            stop: 0.6 #20495f,
            stop: 1 #132b3e
        );
        border-radius: 26px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    QLabel#railEyebrow {
        color: rgba(242, 248, 249, 0.68);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    QLabel#railTitle {
        color: #f5fbfb;
        font-size: 24px;
        font-weight: 700;
    }

    QLabel#railSubtitle {
        color: rgba(239, 248, 247, 0.72);
        font-size: 12px;
        line-height: 1.5;
    }

    QLabel#railSection {
        color: rgba(239, 248, 247, 0.62);
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    QFrame#railStats {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
    }

    QLabel#railStatValue {
        color: #f7fbfc;
        font-size: 22px;
        font-weight: 700;
    }

    QLabel#railStatLabel {
        color: rgba(239, 248, 247, 0.64);
        font-size: 11px;
        font-weight: 600;
    }

    QPushButton[role="nav"] {
        text-align: left;
        padding: 14px 16px;
        border-radius: 16px;
        background: transparent;
        color: rgba(244, 251, 251, 0.78);
        font-size: 14px;
        font-weight: 700;
    }

    QPushButton[role="nav"]:hover {
        background: rgba(255, 255, 255, 0.09);
        color: #f8fffd;
    }

    QPushButton[role="nav"]:checked {
        background: rgba(213, 139, 61, 0.88);
        color: #fffaf3;
    }

    QLabel#railFooter {
        color: rgba(239, 248, 247, 0.55);
        font-size: 11px;
        line-height: 1.5;
    }

    QFrame#workspaceCanvas {
        background: #f6efe5;
        border-radius: 26px;
        border: 1px solid #dfd3c0;
    }

    QStackedWidget#workspaceStack {
        background: #f6efe5;
        border-radius: 22px;
        border: none;
    }

    QWidget#pageScaffold {
        background: transparent;
    }

    QScrollArea#pageScrollArea {
        background: transparent;
        border: none;
    }

    QWidget#pageViewport {
        background: #f6efe5;
        border-radius: 22px;
    }

    QFrame#pageSurface {
        background: #f6efe5;
        border-radius: 22px;
    }

    QFrame#heroBanner {
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 #18344b,
            stop: 0.55 #245a64,
            stop: 1 #d58b3d
        );
        border-radius: 24px;
    }

    QLabel#heroEyebrow {
        color: rgba(248, 255, 253, 0.78);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    QLabel#heroTitle {
        color: #f8fffd;
        font-size: 28px;
        font-weight: 700;
    }

    QLabel#heroSubtitle {
        color: rgba(248, 255, 253, 0.84);
        font-size: 13px;
        line-height: 1.5;
    }

    QLabel#heroMeta {
        color: rgba(255, 249, 239, 0.86);
        font-size: 12px;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.16);
    }

    QFrame#sectionCard {
        background: rgba(255, 252, 246, 0.92);
        border: 1px solid #e4d5be;
        border-radius: 22px;
    }

    QFrame#collapsibleSection {
        background: transparent;
    }

    QFrame#collapsibleSectionBody {
        background: #fbf6ee;
        border: 1px solid #e2d6c5;
        border-radius: 16px;
    }

    QPushButton#collapsibleToggle[role="disclosure"] {
        background: #f6efe2;
        color: #294154;
        border: 1px solid #dfd1bb;
        border-radius: 14px;
        padding: 8px 14px;
        min-height: 38px;
        text-align: left;
        font-size: 12px;
        font-weight: 700;
    }

    QPushButton#collapsibleToggle[role="disclosure"]:hover {
        background: #efe4d2;
        border: 1px solid #d5c3a7;
    }

    QPushButton#collapsibleToggle[role="disclosure"]:pressed {
        background: #e7d8bf;
        border: 1px solid #c9b08b;
    }

    QLabel#workspaceStatusTitle {
        color: #173042;
        font-size: 15px;
        font-weight: 700;
    }

    QLabel#workspaceStatusHighlight {
        color: #0f5e59;
        font-size: 14px;
        font-weight: 700;
        line-height: 1.45;
    }

    QLabel#workspaceStatusMeta {
        color: #5f6f7f;
        font-size: 12px;
        font-weight: 600;
        line-height: 1.5;
    }

    QWidget#workspaceStatusPanel {
        background: #fbf6ee;
        border: 1px solid #e3d7c4;
        border-radius: 16px;
    }

    QWidget#workspaceActionPanel {
        background: transparent;
    }

    QDialog#appMessageDialog {
        background: transparent;
    }

    QFrame#dialogShell {
        background: #fffaf2;
        border: 1px solid #dfd1bb;
        border-radius: 22px;
    }

    QLabel#dialogTitle {
        color: #173042;
        font-size: 18px;
        font-weight: 700;
    }

    QLabel#dialogEyebrow {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    QLabel#dialogEyebrow[tone="info"] {
        color: #3c6a78;
    }

    QLabel#dialogEyebrow[tone="warning"] {
        color: #a86a24;
    }

    QLabel#dialogEyebrow[tone="error"] {
        color: #b04d34;
    }

    QLabel#dialogEyebrow[tone="danger"] {
        color: #b6422c;
    }

    QLabel#dialogMessage {
        color: #556272;
        font-size: 13px;
        line-height: 1.5;
    }

    QTabWidget#requirementTabs::pane {
        border: none;
        background: transparent;
        margin-top: 10px;
    }

    QTabWidget#requirementTabs QTabBar::tab {
        background: #f3e8d6;
        color: #51606e;
        border: 1px solid #ddcfb8;
        border-bottom: none;
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        padding: 10px 18px;
        margin-right: 8px;
        font-size: 13px;
        font-weight: 700;
    }

    QTabWidget#requirementTabs QTabBar::tab:selected {
        background: #fffaf2;
        color: #173042;
    }

    QTabWidget#requirementTabs QTabBar::tab:hover:!selected {
        background: #eee1ca;
    }

    QTextBrowser {
        background: #fffdfa;
        border: 1px solid #d8ccb8;
        border-radius: 16px;
        padding: 14px;
        selection-background-color: #0f766e;
        selection-color: #f8fffd;
    }

    QListView,
    QListWidget,
    QAbstractItemView {
        background: #fffdfa;
        alternate-background-color: #f7f0e2;
        color: #1d2939;
        border: 1px solid #d8ccb8;
        border-radius: 16px;
        gridline-color: #eadfcf;
        selection-background-color: #d7ebe8;
        selection-color: #173042;
    }

    QListView::item,
    QListWidget::item {
        padding: 8px 10px;
        border: none;
    }

    QFrame#structuredTableShell {
        background: #fffdf8;
        border: 1px solid #ded4c5;
        border-radius: 18px;
    }

    QFrame#structuredTableHeader {
        background: transparent;
        border-top-left-radius: 17px;
        border-top-right-radius: 17px;
    }

    QFrame#structuredTableHeaderCell {
        background: transparent;
        border: none;
    }

    QFrame#structuredTableHeaderDivider {
        background: #ece4d8;
        min-width: 1px;
    }

    QFrame#structuredTableHeaderSeparator {
        background: #e5dbce;
        min-height: 1px;
    }

    QLabel#structuredTableHeaderText {
        color: #607283;
        font-size: 12px;
        font-weight: 600;
    }

    QWidget#structuredTableBody {
        background: transparent;
        border-bottom-left-radius: 17px;
        border-bottom-right-radius: 17px;
    }

    QFrame#structuredTableRow {
        background: transparent;
    }

    QFrame#structuredTableCell {
        background: transparent;
    }

    QFrame#structuredTableBodyDivider {
        background: #ece4d8;
        min-width: 1px;
    }

    QFrame#structuredTableRowSeparator {
        background: #e5dbce;
        min-height: 1px;
    }

    QFrame#structuredTableCell[firstCol="true"][lastRow="true"] {
        border-bottom-left-radius: 17px;
    }

    QFrame#structuredTableCell[lastCol="true"][lastRow="true"] {
        border-bottom-right-radius: 17px;
    }

    QLabel#structuredTableCellText {
        color: #24364a;
        font-size: 13px;
        font-weight: 600;
    }

    QListWidget#requirementRecordList {
        background: #fffdfa;
        border: 1px solid #ddd1bf;
        border-radius: 16px;
        padding: 8px;
        outline: 0;
    }

    QListWidget#requirementRecordList::item {
        background: #fff8ef;
        border: 1px solid #eadbc3;
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 6px;
    }

    QListWidget#requirementRecordList::item:hover {
        background: #f9efe0;
        border: 1px solid #dfc9a8;
    }

    QListWidget#requirementRecordList::item:selected {
        background: #e8f3f1;
        color: #173042;
        border: 1px solid #8cbab2;
    }

    QLabel#businessCategoryListSummary {
        color: #607283;
        font-size: 12px;
        font-weight: 700;
    }

    QListWidget#businessCategoryList,
    QListWidget#businessSubcategoryList {
        background: #fcf8f1;
        border: 1px solid #e1d6c5;
        border-radius: 18px;
        padding: 10px;
        outline: 0;
    }

    QListWidget#businessCategoryList::item,
    QListWidget#businessSubcategoryList::item {
        background: transparent;
        border: none;
        padding: 0;
        margin: 0 0 8px 0;
    }

    QFrame#businessCategoryListItem {
        background: #fffdfa;
        border: 1px solid #e6dac7;
        border-radius: 18px;
    }

    QFrame#businessCategoryListItem:hover {
        border: 1px solid #d7c4a4;
        background: #fffaf2;
    }

    QFrame#businessCategoryListItem[selected="true"] {
        background: #edf7f5;
        border: 1px solid #7fb7ae;
    }

    QLabel#businessCategoryListTitle {
        color: #173042;
        font-size: 15px;
        font-weight: 700;
    }

    QLabel#businessCategoryListMeta {
        color: #6a7888;
        font-size: 12px;
        font-weight: 600;
    }

    QFrame#businessCategoryListBadgeShell {
        background: #f6ecdc;
        border: 1px solid #e5cfad;
        border-radius: 999px;
    }

    QLabel#businessCategoryListBadgeText {
        color: #8b5a1f;
        font-size: 12px;
        font-weight: 700;
    }

    QFrame#businessCategoryListItem[selected="true"] QFrame#businessCategoryListBadgeShell {
        background: #d8ece7;
        border: 1px solid #a8d0c8;
    }

    QFrame#businessCategoryListItem[selected="true"] QLabel#businessCategoryListBadgeText {
        color: #155860;
    }

    QFrame#businessCategoryEmptyState {
        background: #f8f3ea;
        border: 1px dashed #d7c8b1;
        border-radius: 16px;
    }

    QLabel#businessCategoryEmptyTitle {
        color: #556879;
        font-size: 13px;
        font-weight: 700;
    }

    QLabel#businessCategoryEmptyText {
        color: #7a8795;
        font-size: 12px;
        font-weight: 600;
        line-height: 1.5;
    }

    QFrame#scenarioHandoffRow {
        background: #fffdfa;
        border: 1px solid #dfd3c1;
        border-radius: 18px;
    }

    QFrame#scenarioHandoffRow:hover {
        border: 1px solid #d2c2a9;
    }

    QLabel#scenarioHandoffId {
        background: #edf7f5;
        color: #1f5963;
        border: 1px solid #cfe3de;
        border-radius: 999px;
        padding: 6px 12px;
        font-size: 11px;
        font-weight: 700;
    }

    QLabel#scenarioHandoffTitle {
        color: #24364a;
        font-size: 15px;
        font-weight: 700;
    }

    QLabel#scenarioHandoffMeta {
        color: #70808f;
        font-size: 12px;
        font-weight: 600;
    }

    QLabel#scenarioHandoffSummary {
        color: #2f4155;
        font-size: 13px;
        font-weight: 600;
        line-height: 1.5;
    }

    QLabel#scenarioHandoffPreview {
        color: #6f7e8d;
        font-size: 12px;
        font-weight: 600;
        line-height: 1.45;
    }

    QLabel#scenarioPriorityBadge {
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 700;
    }

    QLabel#scenarioPriorityBadge[priority="P0"] {
        background: #fde4de;
        color: #a03824;
        border: 1px solid #f3b9ac;
    }

    QLabel#scenarioPriorityBadge[priority="P1"] {
        background: #fff1d8;
        color: #9a611d;
        border: 1px solid #e7c48e;
    }

    QLabel#scenarioPriorityBadge[priority="P2"] {
        background: #e7f1fb;
        color: #1d5c92;
        border: 1px solid #b6d1ec;
    }

    QLabel#scenarioPriorityBadge[priority="P3"] {
        background: #edf2f5;
        color: #5f7181;
        border: 1px solid #d3dde6;
    }

    QWidget#scenarioHandoffActionWrap {
        background: transparent;
    }

    QWidget#scenarioHandoffSelector {
        background: transparent;
        min-height: 34px;
        max-height: 34px;
    }

    QFrame#resultMetricCard {
        background: #fbf4e8;
        border: 1px solid #dfcfb5;
        border-radius: 16px;
    }

    QLabel#resultMetricValue {
        color: #173042;
        font-size: 22px;
        font-weight: 700;
    }

    QLabel#resultMetricLabel {
        color: #5c6776;
        font-size: 11px;
        font-weight: 600;
    }

    QLabel#resultStatus {
        color: #0f766e;
        font-size: 12px;
        font-weight: 700;
    }

    QWidget#resultStatusFeedbackWrap {
        background: transparent;
        min-height: 24px;
    }

    QLabel#resultLoadingIndicator {
        color: #d58b3d;
        font-size: 12px;
        font-weight: 700;
        padding: 3px 10px 3px 10px;
        border-radius: 999px;
        background: rgba(213, 139, 61, 0.14);
        border: 1px solid rgba(213, 139, 61, 0.28);
    }

    QLabel#resultStatusMeta {
        color: #6a7685;
        font-size: 12px;
        font-weight: 600;
    }

    QLabel#sectionTitle {
        color: #12263a;
        font-size: 18px;
        font-weight: 700;
    }

    QLabel#sectionDescription {
        color: #5b6574;
        font-size: 12px;
    }

    QLabel#formLabel {
        color: #3d4754;
        font-size: 13px;
        font-weight: 600;
        padding-right: 8px;
    }

    QLineEdit,
    QPlainTextEdit {
        background: #fffdfa;
        border: 1px solid #d8ccb8;
        border-radius: 14px;
        padding: 12px 14px;
        selection-background-color: #0f766e;
        selection-color: #f8fffd;
    }

    QLineEdit:focus,
    QPlainTextEdit:focus {
        border: 2px solid #0f766e;
    }

    QPlainTextEdit[readOnly="true"] {
        background: #f8f4ec;
        border: 1px solid #d7ccb9;
    }

    QCheckBox {
        spacing: 10px;
        color: #43505e;
        font-weight: 600;
    }

    QCheckBox::indicator {
        width: 20px;
        height: 20px;
        border-radius: 6px;
        border: 1px solid #cbbca5;
        background: #fffdfa;
    }

    QCheckBox::indicator:checked {
        background: #0f766e;
        border: 1px solid #0f766e;
    }

    QPushButton {
        background: #f4ead8;
        color: #173042;
        border: 1px solid #dfd1bb;
        border-radius: 14px;
        padding: 8px 16px;
        min-height: 38px;
        font-size: 13px;
        font-weight: 700;
    }

    QPushButton:hover {
        background: #efe1c8;
        border: 1px solid #d5c09c;
    }

    QPushButton:pressed {
        background: #e2ceab;
        border: 1px solid #c5a97a;
        padding-top: 9px;
        padding-bottom: 7px;
    }

    QPushButton:disabled {
        background: #eee7db;
        color: #97a2ad;
        border: 1px solid #ddd2c3;
    }

    QPushButton[interactionState="busy"] {
        background: #e6f1ee;
        color: #155860;
        border: 1px solid #97bdb7;
    }

    QPushButton[interactionState="busy"]:disabled {
        background: #dce9e6;
        color: #4c6e75;
        border: 1px solid #a8c5bf;
    }

    QPushButton[role="statusChoice"] {
        background: #f9f2e5;
        color: #4e5a68;
        border: 1px solid #dccdb4;
        border-radius: 9px;
        min-height: 30px;
        max-height: 30px;
        padding: 0 9px;
        font-size: 11px;
        font-weight: 700;
    }

    QPushButton[role="statusChoice"]:hover {
        background: #f0e4cf;
    }

    QPushButton[role="statusChoice"]:checked {
        background: #0f766e;
        color: #f8fffd;
        border: 1px solid #0f766e;
    }

    QPushButton[role="primary"] {
        background: #0f766e;
        color: #f8fffd;
        border: 1px solid #0f766e;
    }

    QPushButton[role="primary"]:hover {
        background: #0c645e;
        border: 1px solid #0a5a55;
    }

    QPushButton[role="primary"]:pressed {
        background: #0a5752;
        border: 1px solid #084a46;
    }

    QPushButton[role="primary"]:disabled {
        background: #7daea8;
        color: #eef8f6;
        border: 1px solid #7daea8;
    }

    QPushButton[role="primary"][interactionState="busy"],
    QPushButton[role="primary"][interactionState="busy"]:disabled {
        background: #d8ece7;
        color: #155860;
        border: 1px solid #9bc4bc;
    }

    QPushButton[role="secondary"] {
        background: #e3edf0;
        color: #21465d;
        border: 1px solid #cfdee3;
    }

    QPushButton[role="secondary"]:hover {
        background: #d6e6eb;
        border: 1px solid #b8d0d8;
    }

    QPushButton[role="secondary"]:pressed {
        background: #cadde4;
        border: 1px solid #9bb9c4;
    }

    QPushButton[role="secondary"]:disabled {
        background: #e8eef0;
        color: #92a3b0;
        border: 1px solid #d7e1e5;
    }

    QPushButton[role="secondary"][interactionState="busy"],
    QPushButton[role="secondary"][interactionState="busy"]:disabled {
        background: #dce9e6;
        color: #2a5762;
        border: 1px solid #a8c5bf;
    }

    QPushButton[role="danger"] {
        background: #c55a41;
        color: #fffaf4;
        border: 1px solid #c55a41;
    }

    QPushButton[role="danger"]:hover {
        background: #b14d35;
        border: 1px solid #9f432d;
    }

    QPushButton[role="danger"]:pressed {
        background: #983d28;
        border: 1px solid #813220;
    }

    QPushButton[role="danger"]:disabled {
        background: #dca796;
        color: #fff7f2;
        border: 1px solid #dca796;
    }

    QPushButton[role="danger"][interactionState="busy"],
    QPushButton[role="danger"][interactionState="busy"]:disabled {
        background: #f3ddd5;
        color: #9a402b;
        border: 1px solid #deb2a6;
    }

    QScrollArea {
        border: none;
        background: transparent;
    }

    QSplitter::handle {
        background: transparent;
        width: 10px;
        height: 10px;
    }
    """
