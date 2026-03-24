from __future__ import annotations

from pydantic import BaseModel

from local_test_agent.agents.base import BaseStructuredAgent
from local_test_agent.adapters.llm import LLMAdapter
from local_test_agent.config import LLMSettings
from local_test_agent.store.llm_log_store import LLMLogStore


def test_llm_adapter_formats_socks_proxy_error(monkeypatch):
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:7890")
    adapter = LLMAdapter(LLMSettings())

    message = adapter._build_connection_error_message(
        RuntimeError(
            "Using SOCKS proxy, but the 'socksio' package is not installed. "
            "Make sure to install httpx using `pip install httpx[socks]`."
        )
    )

    assert "SOCKS 代理" in message
    assert "socks5://127.0.0.1:7890" in message
    assert "httpx[socks]" in message


def test_llm_adapter_build_agent_uses_output_type(monkeypatch):
    recorded: dict[str, object] = {}

    class DemoOutput(BaseModel):
        reply: str = ""

    class FakeAgent:
        def __init__(self, model, **kwargs):
            recorded["model"] = model
            recorded["kwargs"] = kwargs

    monkeypatch.setattr("local_test_agent.adapters.llm.Agent", FakeAgent)

    adapter = LLMAdapter(
        LLMSettings(
            provider_model="openai:gpt-4.1-mini",
            api_key="demo-key",
            enable_live_llm=True,
        )
    )

    agent = adapter.build_agent(system_prompt="demo", output_type=DemoOutput)

    assert agent is not None
    assert recorded["kwargs"]["output_type"] is DemoOutput
    assert "result_type" not in recorded["kwargs"]


def test_llm_adapter_reports_structured_output_incompatibility(monkeypatch):
    class FakeRunResult:
        def __init__(self, output):
            self.output = output

    class FakeAgent:
        call_index = 0

        def __init__(self, _model, **_kwargs):
            pass

        def run_sync(self, _prompt):
            FakeAgent.call_index += 1
            if FakeAgent.call_index == 1:
                return FakeRunResult("连接成功")
            raise RuntimeError(
                "Invalid response from openai chat completions endpoint: "
                "choices.0.message.tool_calls.0..."
            )

    monkeypatch.setattr("local_test_agent.adapters.llm.Agent", FakeAgent)
    class FakeOpenAIModel:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIModel", FakeOpenAIModel)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIProvider", lambda **_kwargs: object())

    adapter = LLMAdapter(
        LLMSettings(
            provider_model="openai:gpt-4.1-mini",
            api_key="demo-key",
            enable_live_llm=True,
        )
    )

    result = adapter.test_connection()

    assert result.success is False
    assert result.basic_connectivity_ok is True
    assert result.structured_output_ok is False
    assert "基础模型调用已经成功" in result.message
    assert result.response_excerpt == "连接成功"


def test_structured_agent_logs_empty_output_and_falls_back(monkeypatch, tmp_path):
    class DemoOutput(BaseModel):
        reply: str = ""

    class DemoAgent(BaseStructuredAgent[DemoOutput]):
        system_prompt = "demo"
        output_type = DemoOutput

        def build_prompt(self, *_args, **_kwargs) -> str:
            return "demo"

    class FakeRunResult:
        def __init__(self, output):
            self.output = output

    class FakeAgent:
        def __init__(self, _model, **_kwargs):
            pass

        def run_sync(self, _prompt):
            return FakeRunResult(DemoOutput())

    class FakeOpenAIModel:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("local_test_agent.adapters.llm.Agent", FakeAgent)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIModel", FakeOpenAIModel)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIProvider", lambda **_kwargs: object())

    log_store = LLMLogStore(tmp_path / "llm_calls.log")
    adapter = LLMAdapter(
        LLMSettings(
            provider_model="openai:gpt-4.1-mini",
            api_key="demo-key",
            enable_live_llm=True,
        ),
        log_store=log_store,
    )

    result = DemoAgent(adapter).run_structured("演示 prompt", DemoOutput(reply="规则回退"))
    logs = log_store.read_recent(limit=1)

    assert result.reply == "规则回退"
    assert len(logs) == 1
    assert logs[0].operation == "DemoAgent"
    assert logs[0].used_fallback is True
    assert logs[0].empty_output is True
    assert logs[0].fallback_reason == "empty_structured_output"
