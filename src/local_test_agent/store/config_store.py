from __future__ import annotations

import json
from pathlib import Path

from local_test_agent.adapters.secret_store import SecretStore
from local_test_agent.config import AppSettings


class ConfigStore:
    """统一配置入口。

    目标是让外层只感知一个配置仓库：
    - 非敏感配置统一保存在 app_config.json
    - 敏感凭证统一通过同一仓库读写，底层仍优先使用系统钥匙串
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._default_settings = AppSettings()

    def load(self) -> AppSettings:
        config_path = self._get_existing_config_path()
        if config_path.exists():
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            settings = AppSettings.model_validate(payload)
        else:
            settings = AppSettings()
        self._resolve_storage_paths(settings)
        secret_store = SecretStore(settings.storage.secrets_file)
        settings.llm.api_key = secret_store.get_secret("llm_api_key")
        settings.yunxiao.access_token = secret_store.get_secret("yunxiao_access_token")
        return settings

    def save(self, settings: AppSettings) -> None:
        self._resolve_storage_paths(settings)
        secret_store = SecretStore(settings.storage.secrets_file)
        secret_store.set_secret("llm_api_key", settings.llm.api_key)
        secret_store.set_secret("yunxiao_access_token", settings.yunxiao.access_token)

        serializable_settings = settings.model_dump(mode="json")
        serializable_settings["llm"]["api_key"] = ""
        serializable_settings["yunxiao"]["access_token"] = ""

        settings.config_file.parent.mkdir(parents=True, exist_ok=True)
        settings.config_file.write_text(
            json.dumps(serializable_settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def export_flat_payload(self, settings: AppSettings) -> dict[str, str]:
        secret_store = SecretStore(settings.storage.secrets_file)
        return {
            "config_file": str(settings.config_file),
            "llm_provider_model": settings.llm.provider_model,
            "llm_base_url": settings.llm.base_url,
            "llm_api_key": secret_store.get_secret("llm_api_key"),
            "llm_enable_live": str(settings.llm.enable_live_llm).lower(),
            "yunxiao_api_base_url": settings.yunxiao.api_base_url,
            "yunxiao_organization_id": settings.yunxiao.organization_id,
            "yunxiao_project_id": settings.yunxiao.project_id,
            "yunxiao_access_token": secret_store.get_secret("yunxiao_access_token"),
            "yunxiao_create_defect_path": settings.yunxiao.create_defect_path,
            "database_path": str(settings.storage.database_path),
            "reports_dir": str(settings.storage.reports_dir),
            "artifacts_dir": str(settings.storage.artifacts_dir),
            "llm_logs_path": str(settings.storage.llm_logs_path),
            "runtime_logs_path": str(settings.storage.runtime_logs_path),
            "business_category_count": str(len(settings.business.categories)),
        }

    def _get_existing_config_path(self) -> Path:
        default_config_path = self._project_path(self._default_settings.config_file)
        legacy_config_path = self._project_path(self._default_settings.legacy_config_file)
        if default_config_path.exists():
            return default_config_path
        if legacy_config_path.exists():
            return legacy_config_path
        return default_config_path

    def _resolve_storage_paths(self, settings: AppSettings) -> None:
        settings.storage.app_dir = self._project_path(settings.storage.app_dir)
        settings.storage.database_path = self._project_path(settings.storage.database_path)
        settings.storage.reports_dir = self._project_path(settings.storage.reports_dir)
        settings.storage.artifacts_dir = self._project_path(settings.storage.artifacts_dir)
        settings.storage.secrets_file = self._project_path(settings.storage.secrets_file)
        settings.storage.llm_logs_path = self._project_path(settings.storage.llm_logs_path)
        settings.storage.runtime_logs_path = self._project_path(settings.storage.runtime_logs_path)

    def _project_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return self.project_root / path
