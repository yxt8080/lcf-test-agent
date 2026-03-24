from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from local_test_agent.models import BusinessCategory


class LLMSettings(BaseModel):
    provider_model: str = Field(
        default="openai:gpt-4o-mini",
        description="PydanticAI 使用的模型标识，默认保留 OpenAI 兼容写法。",
    )
    base_url: str = Field(default="", description="Azure/OpenAI 兼容接口地址。")
    api_key: str = Field(default="", description="模型访问凭证。")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    enable_live_llm: bool = Field(
        default=False,
        description="为避免未配置时报错，默认关闭实时模型调用，走本地规则回退。",
    )


class YunxiaoSettings(BaseModel):
    api_base_url: str = Field(default="", description="云效开放平台根地址。")
    organization_id: str = Field(default="", description="组织标识。")
    project_id: str = Field(default="", description="项目标识。")
    access_token: str = Field(default="", description="访问令牌。")
    create_defect_path: str = Field(
        default="/defects",
        description="缺陷创建接口路径，保留可配置是为了适配不同租户的接口网关。",
    )
    upload_attachment_path: str = Field(
        default="/attachments",
        description="附件上传接口路径。",
    )
    defect_type: str = Field(default="bug", description="默认缺陷类型。")


class StorageSettings(BaseModel):
    app_dir: Path = Field(default=Path("data"))
    database_path: Path = Field(default=Path("data/test_agent.db"))
    reports_dir: Path = Field(default=Path("data/reports"))
    artifacts_dir: Path = Field(default=Path("data/artifacts"))
    secrets_file: Path = Field(default=Path("data/.secrets.json"))
    llm_logs_path: Path = Field(default=Path("data/llm_calls.log"))
    runtime_logs_path: Path = Field(default=Path("data/runtime_events.log"))


class BusinessSettings(BaseModel):
    categories: list[BusinessCategory] = Field(
        default_factory=list,
        description="统一维护业务分类字典，供页面和后续模块选择归属业务。",
    )


class AppSettings(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    yunxiao: YunxiaoSettings = Field(default_factory=YunxiaoSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    business: BusinessSettings = Field(default_factory=BusinessSettings)

    @property
    def config_file(self) -> Path:
        return self.storage.app_dir / "app_config.json"

    @property
    def legacy_config_file(self) -> Path:
        return self.storage.app_dir / "settings.json"
