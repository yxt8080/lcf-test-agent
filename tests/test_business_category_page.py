from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from local_test_agent.models import BusinessCategory, BusinessSubcategory
from local_test_agent.ui.pages.business_category_page import BusinessCategoryPage


@pytest.fixture()
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def test_controller_business_category_options_flatten_leaf_paths(controller):
    controller.save_business_categories(
        [
            BusinessCategory(
                code="trade",
                name="交易中心",
                children=[
                    BusinessSubcategory(code="order", name="下单"),
                    BusinessSubcategory(code="refund", name="退款"),
                ],
            ),
            BusinessCategory(code="ops", name="运营平台"),
        ]
    )

    options = controller.list_business_category_options()

    assert [item.value for item in options] == ["trade/order", "trade/refund", "ops"]
    assert [item.label for item in options] == ["交易中心 / 下单", "交易中心 / 退款", "运营平台"]


def test_business_category_page_can_add_and_save_categories(controller, qapp, monkeypatch):
    shown_messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "local_test_agent.ui.pages.business_category_page.show_info_dialog",
        lambda *_args, title, message, **_kwargs: shown_messages.append((title, message)),
    )

    page = BusinessCategoryPage(controller)
    page._add_category()
    page.category_code_input.setText("trade")
    page.category_name_input.setText("交易中心")
    page._apply_category_edit()

    page._add_child()
    page.child_code_input.setText("order")
    page.child_name_input.setText("下单")
    page._apply_child_edit()
    page._save_all()

    categories = controller.list_business_categories()
    assert len(categories) == 1
    assert categories[0].code == "trade"
    assert categories[0].children[0].code == "order"
    assert shown_messages[-1][0] == "保存成功"

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_business_category_page_requires_selected_parent_for_child(controller, qapp, monkeypatch):
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "local_test_agent.ui.pages.business_category_page.show_warning_dialog",
        lambda *_args, title, message, **_kwargs: warnings.append((title, message)),
    )

    page = BusinessCategoryPage(controller)
    page._add_child()

    assert warnings
    assert "请先选择一个一级分类" in warnings[-1][1]
    assert controller.list_business_categories() == []

    page.close()
    page.deleteLater()
    qapp.processEvents()
