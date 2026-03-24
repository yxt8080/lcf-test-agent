from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from time import monotonic
from typing import Generic, TypeVar

from pydantic import BaseModel

from local_test_agent.adapters.llm import LLMAdapter

OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseStructuredAgent(ABC, Generic[OutputT]):
    system_prompt: str
    output_type: type[OutputT]

    def __init__(self, llm_adapter: LLMAdapter) -> None:
        self.llm_adapter = llm_adapter

    def run_structured(
        self,
        prompt: str,
        fallback_result: OutputT,
        *,
        log_context: Mapping[str, object] | None = None,
    ) -> OutputT:
        agent = self.llm_adapter.build_agent(
            system_prompt=self.system_prompt,
            output_type=self.output_type,
        )
        if agent is None:
            # 实时模型不可用时显式记录回退原因，避免页面只看到空结果却不知道其实没发起远端调用。
            self.llm_adapter.log_call(
                operation=self.__class__.__name__,
                success=False,
                used_fallback=True,
                fallback_reason="live_llm_disabled_or_dependency_missing",
                prompt_preview=prompt,
                response_preview=self.llm_adapter.format_output_preview(fallback_result),
                context=dict(log_context or {}),
            )
            return fallback_result
        started_at = monotonic()
        try:
            result = agent.run_sync(prompt)
            output = result.output
            elapsed_ms = int((monotonic() - started_at) * 1000)
            is_valid, invalid_reason = self.validate_output(output)
            if not is_valid:
                self.llm_adapter.log_call(
                    operation=self.__class__.__name__,
                    success=False,
                    used_fallback=True,
                    elapsed_ms=elapsed_ms,
                    empty_output=self.llm_adapter.is_effectively_empty_output(output),
                    fallback_reason=invalid_reason,
                    prompt_preview=prompt,
                    response_preview=self.llm_adapter.format_output_preview(output),
                    context=dict(log_context or {}),
                )
                return fallback_result
            self.llm_adapter.log_call(
                operation=self.__class__.__name__,
                success=True,
                used_fallback=False,
                elapsed_ms=elapsed_ms,
                prompt_preview=prompt,
                response_preview=self.llm_adapter.format_output_preview(output),
                context=dict(log_context or {}),
            )
            return output
        except Exception as exc:
            # 第一版以稳定完成测试工作为主，模型异常不能阻断主流程。
            self.llm_adapter.log_call(
                operation=self.__class__.__name__,
                success=False,
                used_fallback=True,
                elapsed_ms=int((monotonic() - started_at) * 1000),
                fallback_reason="agent_exception",
                error_message=str(exc),
                prompt_preview=prompt,
                response_preview=self.llm_adapter.format_output_preview(fallback_result),
                context=dict(log_context or {}),
            )
            return fallback_result

    def validate_output(self, output: OutputT) -> tuple[bool, str]:
        if self.llm_adapter.is_effectively_empty_output(output):
            return False, "empty_structured_output"
        return True, ""

    @abstractmethod
    def build_prompt(self, *args, **kwargs) -> str:
        raise NotImplementedError
