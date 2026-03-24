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
    PageScaffold,
    SectionCard,
    StructuredResultView,
    ask_confirmation,
    begin_async_button_feedback,
    build_form_label,
    build_primary_button,
    build_secondary_button,
    configure_form_layout,
    configure_line_input,
    configure_text_input,
    show_error_dialog,
    show_info_dialog,
)


class SettingsPage(QWidget):
    def __init__(self, controller, runner: BackgroundRunner | None = None) -> None:
        super().__init__()
        self.controller = controller
        self.runner = runner or BackgroundRunner()
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        scaffold = PageScaffold(
            "配置中心与运行状态",
            "模型配置与云效配置保留在同一页展示，但拆成独立区域分别保存；模型支持先试连通性，再决定是否落盘。",
            meta="配置中心",
        )
        layout = scaffold.content_layout
        page_splitter = QSplitter(Qt.Horizontal)
        page_splitter.setChildrenCollapsible(False)

        self.llm_provider_model = QLineEdit()
        self.llm_base_url = QLineEdit()
        self.llm_api_key = QLineEdit()
        self.llm_enable_live = QCheckBox("启用实时 LLM")
        self.yunxiao_api_base_url = QLineEdit()
        self.yunxiao_organization_id = QLineEdit()
        self.yunxiao_project_id = QLineEdit()
        self.yunxiao_access_token = QLineEdit()
        self.yunxiao_create_defect_path = QLineEdit()

        configure_line_input(self.llm_provider_model, min_width=520)
        configure_line_input(self.llm_base_url, min_width=520)
        configure_line_input(self.llm_api_key, min_width=520)
        configure_line_input(self.yunxiao_api_base_url, min_width=520)
        configure_line_input(self.yunxiao_organization_id, min_width=520)
        configure_line_input(self.yunxiao_project_id, min_width=520)
        configure_line_input(self.yunxiao_access_token, min_width=520)
        configure_line_input(self.yunxiao_create_defect_path, min_width=520)

        self.llm_api_key.setEchoMode(QLineEdit.Password)
        self.yunxiao_access_token.setEchoMode(QLineEdit.Password)

        self.llm_provider_model.setPlaceholderText("例如：openai:gpt-4o-mini")
        self.llm_base_url.setPlaceholderText("Azure/OpenAI 兼容接口地址；留空则走官方默认地址")
        self.yunxiao_api_base_url.setPlaceholderText("云效开放平台根地址")
        self.yunxiao_create_defect_path.setPlaceholderText("/defects")

        llm_form = QFormLayout()
        configure_form_layout(llm_form)
        llm_form.addRow(build_form_label("模型标识"), self.llm_provider_model)
        llm_form.addRow(build_form_label("模型 Base URL"), self.llm_base_url)
        llm_form.addRow(build_form_label("模型 API Key"), self.llm_api_key)
        llm_form.addRow(build_form_label("实时模型"), self.llm_enable_live)

        self.llm_save_button = build_primary_button("保存模型配置")
        self.llm_save_button.clicked.connect(self._save_llm_settings)
        self.llm_test_button = build_secondary_button("测试模型配置")
        self.llm_test_button.clicked.connect(self._test_llm_settings)

        llm_card = SectionCard(
            "模型配置",
            "该区域只保存大模型相关参数。建议先点“测试模型配置”确认当前输入可用，再决定是否正式保存。",
        )
        llm_card.body_layout.addLayout(llm_form)
        llm_card.body_layout.addWidget(self.llm_save_button)
        llm_card.body_layout.addWidget(self.llm_test_button)

        yunxiao_form = QFormLayout()
        configure_form_layout(yunxiao_form)
        yunxiao_form.addRow(build_form_label("云效 API"), self.yunxiao_api_base_url)
        yunxiao_form.addRow(build_form_label("组织 ID"), self.yunxiao_organization_id)
        yunxiao_form.addRow(build_form_label("项目 ID"), self.yunxiao_project_id)
        yunxiao_form.addRow(build_form_label("云效 Token"), self.yunxiao_access_token)
        yunxiao_form.addRow(build_form_label("提单路径"), self.yunxiao_create_defect_path)

        self.yunxiao_save_button = build_primary_button("保存云效配置")
        self.yunxiao_save_button.clicked.connect(self._save_yunxiao_settings)

        yunxiao_card = SectionCard(
            "云效配置",
            "该区域只保存云效接入参数。即使暂未配置完整，报告与缺陷流程也会先退回本地草稿。",
        )
        yunxiao_card.body_layout.addLayout(yunxiao_form)
        yunxiao_card.body_layout.addWidget(self.yunxiao_save_button)

        security_card = SectionCard("配置说明", "敏感字段优先写入系统钥匙串，不会直接明文落到主配置文件。")
        security_label = QLabel(
            "1. 模型配置与云效配置分别保存，避免修改一类配置时误覆盖另一类配置。\n"
            "2. 模型测试默认读取当前页面输入值，不要求先保存。\n"
            "3. 若未启用实时模型，Agent 仍会走本地规则回退。\n"
            "4. 运行状态只负责展示当前已加载的本地配置与数据目录。"
        )
        security_label.setWordWrap(True)
        security_card.body_layout.addWidget(security_label)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)
        left_layout.addWidget(llm_card)
        left_layout.addWidget(yunxiao_card)
        left_layout.addWidget(security_card)
        left_layout.addStretch(1)

        self.llm_test_view = StructuredResultView(
            "点击“测试模型配置”后，这里会展示是否真正发起了模型调用，以及当前配置是否生效。"
        )
        llm_test_card = SectionCard("模型测试结果", "用于核对当前页面里的模型参数是否能真实完成一次最小调用。")
        llm_test_card.body_layout.addWidget(self.llm_test_view)

        self.llm_log_output = QPlainTextEdit()
        self.llm_log_output.setReadOnly(True)
        self.llm_log_output.setPlaceholderText("这里会展示最近的大模型调用日志。")
        configure_text_input(self.llm_log_output, min_width=620, min_height=240)
        self.refresh_llm_logs_button = build_secondary_button("刷新模型日志")
        self.refresh_llm_logs_button.clicked.connect(self._refresh_llm_logs)
        self.clear_llm_logs_button = build_secondary_button("清空模型日志")
        self.clear_llm_logs_button.clicked.connect(self._clear_llm_logs)

        llm_log_card = SectionCard("模型调用日志", "用于排查模型空返回、结构化输出失败和自动回退等问题。")
        llm_log_card.body_layout.addWidget(self.llm_log_output)
        llm_log_card.body_layout.addWidget(self.refresh_llm_logs_button)
        llm_log_card.body_layout.addWidget(self.clear_llm_logs_button)

        self.runtime_log_output = QPlainTextEdit()
        self.runtime_log_output.setReadOnly(True)
        self.runtime_log_output.setPlaceholderText("这里会展示最近的运行日志。")
        configure_text_input(self.runtime_log_output, min_width=620, min_height=240)
        self.refresh_runtime_logs_button = build_secondary_button("刷新运行日志")
        self.refresh_runtime_logs_button.clicked.connect(self._refresh_runtime_logs)
        self.clear_runtime_logs_button = build_secondary_button("清空运行日志")
        self.clear_runtime_logs_button.clicked.connect(self._clear_runtime_logs)

        runtime_log_card = SectionCard("运行日志", "用于排查工作流执行、降级分支和后台线程异常。")
        runtime_log_card.body_layout.addWidget(self.runtime_log_output)
        runtime_log_card.body_layout.addWidget(self.refresh_runtime_logs_button)
        runtime_log_card.body_layout.addWidget(self.clear_runtime_logs_button)

        self.runtime_view = StructuredResultView(
            "这里会展示当前配置文件、数据库和运行时状态的结构化摘要。"
        )
        self.refresh_button = build_secondary_button("刷新运行状态")
        self.refresh_button.clicked.connect(self._refresh_runtime)
        runtime_card = SectionCard("运行状态", "用于确认当前已保存配置、数据库和报告目录是否已正确加载。")
        runtime_card.body_layout.addWidget(self.runtime_view)
        runtime_card.body_layout.addWidget(self.refresh_button)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(18)
        right_layout.addWidget(llm_test_card)
        right_layout.addWidget(llm_log_card)
        right_layout.addWidget(runtime_log_card)
        right_layout.addWidget(runtime_card)
        right_layout.addStretch(1)

        page_splitter.addWidget(left_panel)
        page_splitter.addWidget(right_panel)
        page_splitter.setStretchFactor(0, 4)
        page_splitter.setStretchFactor(1, 5)

        layout.addWidget(page_splitter)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scaffold)

    def _collect_llm_payload(self) -> dict[str, str]:
        return {
            "llm_provider_model": self.llm_provider_model.text(),
            "llm_base_url": self.llm_base_url.text(),
            "llm_api_key": self.llm_api_key.text(),
            "llm_enable_live": "true" if self.llm_enable_live.isChecked() else "false",
        }

    def _collect_yunxiao_payload(self) -> dict[str, str]:
        return {
            "yunxiao_api_base_url": self.yunxiao_api_base_url.text(),
            "yunxiao_organization_id": self.yunxiao_organization_id.text(),
            "yunxiao_project_id": self.yunxiao_project_id.text(),
            "yunxiao_access_token": self.yunxiao_access_token.text(),
            "yunxiao_create_defect_path": self.yunxiao_create_defect_path.text(),
        }

    def _load_settings(self) -> None:
        payload = self.controller.load_settings()
        self.llm_provider_model.setText(payload.get("llm_provider_model", ""))
        self.llm_base_url.setText(payload.get("llm_base_url", ""))
        self.llm_api_key.setText(payload.get("llm_api_key", ""))
        self.llm_enable_live.setChecked(payload.get("llm_enable_live", "false") == "true")
        self.yunxiao_api_base_url.setText(payload.get("yunxiao_api_base_url", ""))
        self.yunxiao_organization_id.setText(payload.get("yunxiao_organization_id", ""))
        self.yunxiao_project_id.setText(payload.get("yunxiao_project_id", ""))
        self.yunxiao_access_token.setText(payload.get("yunxiao_access_token", ""))
        self.yunxiao_create_defect_path.setText(payload.get("yunxiao_create_defect_path", ""))
        self._refresh_runtime()
        self._refresh_llm_logs()
        self._refresh_runtime_logs()

    def _save_llm_settings(self) -> None:
        self.controller.save_llm_settings(self._collect_llm_payload())
        show_info_dialog(self, title="模型配置已保存", message="模型配置已保存到本地。")
        self._refresh_runtime()

    def _save_yunxiao_settings(self) -> None:
        self.controller.save_yunxiao_settings(self._collect_yunxiao_payload())
        show_info_dialog(self, title="云效配置已保存", message="云效配置已保存到本地。")
        self._refresh_runtime()

    def _test_llm_settings(self) -> None:
        self.llm_test_view.set_loading("正在验证模型配置...", show_thinking_feedback=True)
        on_success, on_error = begin_async_button_feedback(
            self.llm_test_button,
            busy_text="测试中...",
            on_success=self._show_llm_test_result,
            on_error=self._show_llm_test_error,
            disable_widgets=[self.llm_save_button],
        )
        self.runner.submit(
            self.controller.test_llm_settings,
            self._collect_llm_payload(),
            on_success=on_success,
            on_error=on_error,
        )

    def _show_llm_test_result(self, result) -> None:
        endpoint_text = result.base_url or "官方默认地址"
        response_text = result.response_excerpt or "本次未返回额外文本。"
        summary_sections = []
        if not result.success:
            # 失败原因单独高亮，避免用户只看到“失败”状态却还要自己在摘要中找细节。
            summary_sections.append(
                "<div style='background:#fff1ef;border:1px solid #f0b4aa;border-radius:12px;padding:14px 16px;'>"
                "<h3 style='margin:0 0 8px 0;color:#9f2d20;'>失败原因</h3>"
                f"<p style='margin:0;color:#6b241b;'>{escape(result.message)}</p>"
                "</div>"
            )
        summary_sections.extend(
            [
                f"<h3>测试结论</h3><p>{escape(result.message)}</p>",
                "<h3>诊断阶段</h3><ul>"
                f"<li>基础调用：{'通过' if result.basic_connectivity_ok else '未通过'}</li>"
                f"<li>结构化输出：{'通过' if result.structured_output_ok else '未通过'}</li>"
                "</ul>",
                f"<h3>请求目标</h3><p>模型：{escape(result.provider_model or '未填写')}<br/>地址：{escape(endpoint_text)}</p>",
                f"<h3>模型返回</h3><p>{escape(response_text)}</p>",
            ]
        )
        summary_html = "\n".join(summary_sections)
        self.llm_test_view.set_result(
            status="模型配置测试通过" if result.success else "模型配置测试未通过",
            metrics=[
                ("通过" if result.success else "失败", "测试结果"),
                ("通过" if result.basic_connectivity_ok else "失败", "基础调用"),
                ("通过" if result.structured_output_ok else "失败", "结构化输出"),
                ("已启用" if result.live_mode_enabled else "未启用", "实时模型"),
            ],
            summary_html=summary_html,
            payload=result.model_dump(mode="json"),
        )
        self._refresh_llm_logs()
        if not result.success:
            show_error_dialog(self, title="模型配置测试未通过", message=result.message)

    def _show_llm_test_error(self, message: str) -> None:
        self.llm_test_view.set_result(
            status="模型配置测试失败",
            metrics=[],
            summary_html=f"<h3>失败原因</h3><p>{escape(message)}</p>",
            payload=None,
        )
        show_error_dialog(self, title="模型配置测试失败", message=message)
        self._refresh_llm_logs()

    def _refresh_runtime(self) -> None:
        payload = self.controller.export_runtime_state()
        database = payload.get("database", {})
        settings = payload.get("settings", {})
        summary_html = "\n".join(
            [
                f"<h3>主配置文件</h3><p>{escape(settings.get('config_file', '未找到'))}</p>",
                "<h3>目录与存储</h3><ul>"
                f"<li>数据库：{escape(settings.get('database_path', ''))}</li>"
                f"<li>报告目录：{escape(settings.get('reports_dir', ''))}</li>"
                f"<li>产物目录：{escape(settings.get('artifacts_dir', ''))}</li>"
                f"<li>模型日志：{escape(settings.get('llm_logs_path', ''))}</li>"
                f"<li>运行日志：{escape(settings.get('runtime_logs_path', ''))}</li>"
                "</ul>",
            ]
        )
        counts = database.get("counts", {})
        self.runtime_view.set_result(
            status="运行状态已刷新",
            metrics=[
                (str(counts.get("requirements", 0)), "需求"),
                (str(counts.get("scenarios", 0)), "场景"),
                (str(counts.get("executions", 0)), "执行"),
                (str(counts.get("defect_drafts", 0)), "草稿"),
            ],
            summary_html=summary_html,
            payload=payload,
        )

    def _refresh_llm_logs(self) -> None:
        entries = self.controller.list_recent_llm_logs(limit=50)
        self.llm_log_output.setPlainText(self._format_llm_logs(entries))

    def _clear_llm_logs(self) -> None:
        confirmed = ask_confirmation(
            self,
            title="清空模型日志",
            message="清空后将移除当前本地模型调用日志，仅用于诊断排查，是否继续？",
            confirm_text="确认清空",
        )
        if not confirmed:
            return
        self.controller.clear_llm_logs()
        self._refresh_llm_logs()
        show_info_dialog(self, title="日志已清空", message="本地模型调用日志已清空。")

    def _refresh_runtime_logs(self) -> None:
        entries = self.controller.list_recent_runtime_logs(limit=80)
        self.runtime_log_output.setPlainText(self._format_runtime_logs(entries))

    def _clear_runtime_logs(self) -> None:
        confirmed = ask_confirmation(
            self,
            title="清空运行日志",
            message="清空后将移除当前本地运行日志，仅用于诊断排查，是否继续？",
            confirm_text="确认清空",
        )
        if not confirmed:
            return
        self.controller.clear_runtime_logs()
        self._refresh_runtime_logs()
        show_info_dialog(self, title="日志已清空", message="本地运行日志已清空。")

    @staticmethod
    def _format_llm_logs(entries: list) -> str:
        if not entries:
            return "当前还没有模型调用日志。"

        blocks: list[str] = []
        for entry in entries:
            blocks.append(
                "\n".join(
                    [
                        f"[{entry.occurred_at.astimezone().strftime('%Y-%m-%d %H:%M:%S')}] {entry.operation}",
                        f"结果：{'成功' if entry.success else '失败'} · 已回退：{'是' if entry.used_fallback else '否'} · 耗时：{entry.elapsed_ms} ms",
                        f"模型：{entry.provider_model or '未配置'}",
                        f"地址：{entry.base_url or '官方默认地址'}",
                        f"空返回：{'是' if entry.empty_output else '否'}",
                        f"回退原因：{entry.fallback_reason or '无'}",
                        f"错误信息：{entry.error_message or '无'}",
                        f"业务上下文：{entry.context or '无'}",
                        "Prompt 摘录：",
                        entry.prompt_preview or "无",
                        "返回摘录：",
                        entry.response_preview or "无",
                    ]
                )
            )
        return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(blocks)

    @staticmethod
    def _format_runtime_logs(entries: list) -> str:
        if not entries:
            return "当前还没有运行日志。"

        blocks: list[str] = []
        for entry in entries:
            blocks.append(
                "\n".join(
                    [
                        f"[{entry.occurred_at.astimezone().strftime('%Y-%m-%d %H:%M:%S')}] {entry.level.value.upper()} {entry.event}",
                        f"说明：{entry.message}",
                        f"上下文：{entry.context or '无'}",
                        "异常栈：",
                        entry.traceback or "无",
                    ]
                )
            )
        return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(blocks)
