from __future__ import annotations

import json

from local_test_agent.models import BusinessCategory, BusinessSubcategory, LLMConnectionTestResult
from local_test_agent.store.config_store import ConfigStore


def test_config_store_uses_unified_app_config_file(tmp_path):
    store = ConfigStore(tmp_path)
    settings = store.load()
    settings.llm.provider_model = "openai:gpt-4.1-mini"
    settings.llm.base_url = "https://example.invalid/v1"
    settings.llm.api_key = "demo-key"
    settings.yunxiao.project_id = "project-demo"
    settings.yunxiao.access_token = "token-demo"

    store.save(settings)

    config_file = tmp_path / "data" / "app_config.json"
    assert config_file.exists()

    payload = json.loads(config_file.read_text(encoding="utf-8"))
    assert payload["llm"]["provider_model"] == "openai:gpt-4.1-mini"
    assert payload["llm"]["api_key"] == ""
    assert payload["yunxiao"]["access_token"] == ""


def test_config_store_reads_legacy_settings_file(tmp_path):
    legacy_file = tmp_path / "data" / "settings.json"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text(
        json.dumps(
            {
                "llm": {
                    "provider_model": "openai:gpt-4o-mini",
                    "base_url": "",
                    "api_key": "",
                    "temperature": 0.2,
                    "enable_live_llm": False,
                },
                "yunxiao": {
                    "api_base_url": "",
                    "organization_id": "",
                    "project_id": "legacy-project",
                    "access_token": "",
                    "create_defect_path": "/defects",
                    "upload_attachment_path": "/attachments",
                    "defect_type": "bug",
                },
                "storage": {
                    "app_dir": "data",
                    "database_path": "data/test_agent.db",
                    "reports_dir": "data/reports",
                    "artifacts_dir": "data/artifacts",
                    "secrets_file": "data/.secrets.json",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    store = ConfigStore(tmp_path)
    settings = store.load()

    assert settings.yunxiao.project_id == "legacy-project"
    assert settings.config_file.name == "app_config.json"


def test_config_store_persists_business_categories(tmp_path):
    store = ConfigStore(tmp_path)
    settings = store.load()
    settings.business.categories = [
        BusinessCategory(
            code="trade",
            name="交易中心",
            children=[
                BusinessSubcategory(code="order", name="下单"),
                BusinessSubcategory(code="refund", name="退款"),
            ],
        )
    ]

    store.save(settings)

    reloaded = store.load()
    assert len(reloaded.business.categories) == 1
    assert reloaded.business.categories[0].code == "trade"
    assert reloaded.business.categories[0].children[1].name == "退款"


def test_controller_can_save_llm_and_yunxiao_settings_separately(controller):
    controller.save_yunxiao_settings(
        {
            "yunxiao_api_base_url": "https://yunxiao.example.invalid",
            "yunxiao_organization_id": "org-demo",
            "yunxiao_project_id": "project-demo",
            "yunxiao_access_token": "token-demo",
            "yunxiao_create_defect_path": "/bugs",
        }
    )
    controller.save_llm_settings(
        {
            "llm_provider_model": "openai:gpt-4.1-mini",
            "llm_base_url": "https://api.example.invalid/v1",
            "llm_api_key": "llm-demo-key",
            "llm_enable_live": "true",
        }
    )
    payload = controller.load_settings()

    assert payload["llm_provider_model"] == "openai:gpt-4.1-mini"
    assert payload["llm_base_url"] == "https://api.example.invalid/v1"
    assert payload["llm_api_key"] == "llm-demo-key"
    assert payload["yunxiao_project_id"] == "project-demo"
    assert payload["yunxiao_create_defect_path"] == "/bugs"

    controller.save_yunxiao_settings(
        {
            "yunxiao_api_base_url": "https://yunxiao-2.example.invalid",
            "yunxiao_organization_id": "org-updated",
            "yunxiao_project_id": "project-updated",
            "yunxiao_access_token": "token-updated",
            "yunxiao_create_defect_path": "/defects-v2",
        }
    )
    payload = controller.load_settings()

    assert payload["llm_provider_model"] == "openai:gpt-4.1-mini"
    assert payload["llm_api_key"] == "llm-demo-key"
    assert payload["yunxiao_project_id"] == "project-updated"
    assert payload["yunxiao_create_defect_path"] == "/defects-v2"


def test_controller_llm_test_uses_draft_payload_without_persisting(controller, monkeypatch):
    captured: dict[str, str] = {}

    def fake_test_connection(self):
        captured["provider_model"] = self.settings.provider_model
        captured["base_url"] = self.settings.base_url
        captured["api_key"] = self.settings.api_key
        return LLMConnectionTestResult(
            success=True,
            provider_model=self.settings.provider_model,
            base_url=self.settings.base_url,
            live_mode_enabled=self.settings.enable_live_llm,
            message="ok",
            response_excerpt="连接成功",
        )

    monkeypatch.setattr("local_test_agent.controller.workbench_controller.LLMAdapter.test_connection", fake_test_connection)
    original_model = controller.settings.llm.provider_model

    result = controller.test_llm_settings(
        {
            "llm_provider_model": "openai:gpt-4.1",
            "llm_base_url": "https://probe.example.invalid/v1",
            "llm_api_key": "probe-key",
            "llm_enable_live": "true",
        }
    )

    assert result.success is True
    assert captured == {
        "provider_model": "openai:gpt-4.1",
        "base_url": "https://probe.example.invalid/v1",
        "api_key": "probe-key",
    }
    assert controller.settings.llm.provider_model == original_model
