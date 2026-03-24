from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from local_test_agent.config import LLMSettings
from local_test_agent.models import LLMCallLogEntry, LLMConnectionTestResult, LLMProbeReply
from local_test_agent.store.llm_log_store import LLMLogStore

try:
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider
except ImportError:  # pragma: no cover - 依赖未安装时走本地回退
    Agent = None
    OpenAIModel = None
    OpenAIProvider = None


class LLMAdapter:
    def __init__(self, settings: LLMSettings, log_store: LLMLogStore | None = None) -> None:
        self.settings = settings
        self.log_store = log_store

    @property
    def enabled(self) -> bool:
        return bool(
            Agent
            and self.settings.enable_live_llm
            and self.settings.provider_model
            and self.settings.api_key
        )

    def build_agent(
        self,
        *,
        system_prompt: str,
        output_type: type[BaseModel],
    ) -> Agent | None:
        if not self.enabled or Agent is None:
            return None
        model = self._build_model()
        return Agent(model, system_prompt=system_prompt, output_type=output_type)

    def test_connection(self) -> LLMConnectionTestResult:
        provider_model = self.settings.provider_model.strip()
        base_url = self.settings.base_url.strip()
        api_key = self.settings.api_key.strip()

        if Agent is None or OpenAIModel is None or OpenAIProvider is None:
            return LLMConnectionTestResult(
                success=False,
                provider_model=provider_model,
                base_url=base_url,
                live_mode_enabled=self.settings.enable_live_llm,
                basic_connectivity_ok=False,
                structured_output_ok=False,
                message="当前环境未安装实时模型依赖，无法执行连通性测试。",
            )
        if not self.settings.enable_live_llm:
            return LLMConnectionTestResult(
                success=False,
                provider_model=provider_model,
                base_url=base_url,
                live_mode_enabled=False,
                basic_connectivity_ok=False,
                structured_output_ok=False,
                message="当前未启用实时模型，后续分析仍会走本地规则回退。",
            )
        if not provider_model:
            return LLMConnectionTestResult(
                success=False,
                base_url=base_url,
                live_mode_enabled=True,
                basic_connectivity_ok=False,
                structured_output_ok=False,
                message="请先填写模型标识，再执行配置测试。",
            )
        if not api_key:
            return LLMConnectionTestResult(
                success=False,
                provider_model=provider_model,
                base_url=base_url,
                live_mode_enabled=True,
                basic_connectivity_ok=False,
                structured_output_ok=False,
                message="请先填写模型 API Key，再执行配置测试。",
            )

        try:
            basic_probe_agent = Agent(
                self._build_model(),
                system_prompt="你是本地测试智能体的模型连通性探针，请用极短中文确认已收到请求。",
            )
            basic_result = basic_probe_agent.run_sync("请返回一句不超过12个字的中文，说明连接测试成功。")
        except Exception as exc:
            error_message = self._build_connection_error_message(exc)
            self.log_call(
                operation="LLMConnectionTest.basic_probe",
                success=False,
                used_fallback=False,
                error_message=error_message,
                prompt_preview="请返回一句不超过12个字的中文，说明连接测试成功。",
            )
            return LLMConnectionTestResult(
                success=False,
                provider_model=provider_model,
                base_url=base_url,
                live_mode_enabled=True,
                basic_connectivity_ok=False,
                structured_output_ok=False,
                message=f"模型调用失败：{error_message}",
            )

        basic_response_text = self._extract_probe_text(basic_result.output)
        self.log_call(
            operation="LLMConnectionTest.basic_probe",
            success=True,
            used_fallback=False,
            prompt_preview="请返回一句不超过12个字的中文，说明连接测试成功。",
            response_preview=basic_response_text,
        )

        try:
            structured_probe_agent = Agent(
                self._build_model(),
                system_prompt="你是本地测试智能体的结构化输出探针，请返回一个简短 reply 字段。",
                output_type=LLMProbeReply,
            )
            structured_result = structured_probe_agent.run_sync("请返回 reply='结构化测试成功'")
        except Exception as exc:
            error_message = self._build_connection_error_message(exc)
            self.log_call(
                operation="LLMConnectionTest.structured_probe",
                success=False,
                used_fallback=False,
                error_message=error_message,
                prompt_preview="请返回 reply='结构化测试成功'",
                response_preview=basic_response_text,
            )
            if self._looks_like_structured_output_compatibility_error(error_message):
                return LLMConnectionTestResult(
                    success=False,
                    provider_model=provider_model,
                    base_url=base_url,
                    live_mode_enabled=True,
                    basic_connectivity_ok=True,
                    structured_output_ok=False,
                    message=(
                        "基础模型调用已经成功，但当前接口返回的 Chat Completions 工具调用格式"
                        "不兼容 PydanticAI 结构化输出，因此实时结构化分析暂时不可用。"
                    ),
                    response_excerpt=basic_response_text,
                )
            return LLMConnectionTestResult(
                success=False,
                provider_model=provider_model,
                base_url=base_url,
                live_mode_enabled=True,
                basic_connectivity_ok=True,
                structured_output_ok=False,
                message=f"基础调用成功，但结构化输出测试失败：{error_message}",
                response_excerpt=basic_response_text,
            )

        self.log_call(
            operation="LLMConnectionTest.structured_probe",
            success=True,
            used_fallback=False,
            prompt_preview="请返回 reply='结构化测试成功'",
            response_preview=structured_result.output.reply.strip() or basic_response_text,
        )
        return LLMConnectionTestResult(
            success=True,
            provider_model=provider_model,
            base_url=base_url,
            live_mode_enabled=True,
            basic_connectivity_ok=True,
            structured_output_ok=True,
            message="模型调用成功，当前配置已生效。",
            response_excerpt=structured_result.output.reply.strip() or basic_response_text,
        )

    def _build_model(self) -> OpenAIModel | str:
        if self.settings.api_key and OpenAIModel and OpenAIProvider:
            # 配置页填写的凭证必须显式注入 provider，避免只在自定义 base_url 场景下才生效。
            provider_kwargs = {"api_key": self.settings.api_key}
            if self.settings.base_url:
                provider_kwargs["base_url"] = self.settings.base_url
            provider = OpenAIProvider(**provider_kwargs)
            provider_model = self.settings.provider_model.split(":")[-1]
            return OpenAIModel(provider_model, provider=provider)
        return self.settings.provider_model

    def _build_connection_error_message(self, exc: Exception) -> str:
        raw_message = str(exc).strip() or exc.__class__.__name__
        lower_message = raw_message.lower()
        if "socks proxy" in lower_message and "socksio" in lower_message:
            proxy_address = (
                os.environ.get("ALL_PROXY")
                or os.environ.get("all_proxy")
                or os.environ.get("HTTPS_PROXY")
                or os.environ.get("https_proxy")
                or "未检测到代理地址"
            )
            # 当前机器已配置 SOCKS 代理，但 httpx 缺少 socks 扩展时，请求会在建立连接前直接失败。
            return (
                "检测到当前环境启用了 SOCKS 代理 "
                f"({proxy_address})，但运行环境尚未安装 socksio 依赖。"
                " 请安装 `httpx[socks]`，或移除当前会话中的 SOCKS 代理后重试。"
            )
        return raw_message

    def _looks_like_structured_output_compatibility_error(self, message: str) -> bool:
        normalized = message.lower()
        return (
            "invalid response from openai chat completions endpoint" in normalized
            and "tool_calls" in normalized
        )

    def _extract_probe_text(self, output: object) -> str:
        if isinstance(output, str):
            return output.strip()
        if hasattr(output, "reply"):
            reply = getattr(output, "reply")
            if isinstance(reply, str):
                return reply.strip()
        return ""

    def log_call(
        self,
        *,
        operation: str,
        success: bool,
        used_fallback: bool,
        elapsed_ms: int = 0,
        empty_output: bool = False,
        fallback_reason: str = "",
        error_message: str = "",
        prompt_preview: str = "",
        response_preview: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        if self.log_store is None:
            return
        self.log_store.append(
            LLMCallLogEntry(
                operation=operation,
                provider_model=self.settings.provider_model,
                base_url=self.settings.base_url,
                success=success,
                used_fallback=used_fallback,
                live_mode_enabled=self.settings.enable_live_llm,
                elapsed_ms=elapsed_ms,
                empty_output=empty_output,
                fallback_reason=fallback_reason,
                error_message=error_message,
                prompt_preview=self._shorten_text(prompt_preview),
                response_preview=self._shorten_text(response_preview),
                context=self._normalize_context(context or {}),
            )
        )

    def is_effectively_empty_output(self, output: object) -> bool:
        if isinstance(output, BaseModel):
            payload = output.model_dump(mode="json")
            return self._is_effectively_empty_value(payload)
        return self._is_effectively_empty_value(output)

    def format_output_preview(self, output: object) -> str:
        if isinstance(output, BaseModel):
            return output.model_dump_json(indent=2)
        if isinstance(output, Mapping):
            return str(dict(output))
        if isinstance(output, Sequence) and not isinstance(output, (str, bytes, bytearray)):
            return str(list(output))
        return str(output)

    def _is_effectively_empty_value(self, value: object) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, Mapping):
            return all(self._is_effectively_empty_value(item) for item in value.values())
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return all(self._is_effectively_empty_value(item) for item in value)
        if isinstance(value, bool):
            return value is False
        if isinstance(value, (int, float)):
            return value == 0
        return False

    @staticmethod
    def _shorten_text(text: str, limit: int = 1200) -> str:
        normalized = (text or "").strip()
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit]}...(截断)"

    def _normalize_context(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if value in (None, "", [], {}, ()):
                continue
            normalized[str(key)] = self._normalize_context_value(value)
        return normalized

    def _normalize_context_value(self, value: object) -> Any:
        if isinstance(value, Mapping):
            return self._normalize_context(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [self._normalize_context_value(item) for item in list(value)[:10]]
        if isinstance(value, str):
            return self._shorten_text(value, limit=300)
        if isinstance(value, (int, float, bool)):
            return value
        return self._shorten_text(str(value), limit=300)
