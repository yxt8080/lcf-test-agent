from __future__ import annotations

from pydantic import BaseModel, Field

from local_test_agent.agents.base import BaseStructuredAgent
from local_test_agent.models import DefectDraft, ExecutionResult


class DefectDraftPayload(BaseModel):
    requirement_id: str | None = None
    execution_request_id: str
    title: str
    description: str
    repro_steps: list[str] = Field(default_factory=list)
    expected_result: str
    actual_result: str
    attachments: list[str] = Field(default_factory=list)
    yunxiao_fields: dict[str, str] = Field(default_factory=dict)
    report_summary: str = ""

    def to_draft(self) -> DefectDraft:
        return DefectDraft(**self.model_dump())


class DefectDraftAgent(BaseStructuredAgent[DefectDraftPayload]):
    system_prompt = (
        "你是缺陷草稿代理。请根据测试执行结果和证据，输出可供人工确认的 bug 草稿。"
    )
    output_type = DefectDraftPayload

    def build_draft(
        self,
        result: ExecutionResult,
        *,
        requirement_id: str | None = None,
        environment: str = "test",
    ) -> DefectDraft:
        fallback = self._build_fallback(result, requirement_id=requirement_id, environment=environment)
        prompt = self.build_prompt(result, requirement_id=requirement_id, environment=environment)
        payload = self.run_structured(
            prompt,
            fallback,
            log_context={
                "request_id": result.request_id,
                "requirement_id": requirement_id or "",
                "environment": environment,
                "failed_case_count": len(result.failed_cases),
            },
        )
        return payload.to_draft()

    def build_prompt(
        self,
        result: ExecutionResult,
        *,
        requirement_id: str | None = None,
        environment: str = "test",
    ) -> str:
        return "\n".join(
            [
                f"需求 ID: {requirement_id or '未知'}",
                f"执行请求 ID: {result.request_id}",
                f"执行状态: {result.status.value}",
                f"环境: {environment}",
                f"摘要: {result.summary}",
                f"失败用例: {result.failed_cases}",
                f"标准输出: {result.stdout[:4000]}",
                f"错误输出: {result.stderr[:4000]}",
                f"产物: {[item.path for item in result.artifacts]}",
            ]
        )

    def _build_fallback(
        self,
        result: ExecutionResult,
        *,
        requirement_id: str | None = None,
        environment: str = "test",
    ) -> DefectDraftPayload:
        failed_case = result.failed_cases[0] if result.failed_cases else "未知失败场景"
        attachments = [item.path for item in result.artifacts]
        return DefectDraftPayload(
            requirement_id=requirement_id,
            execution_request_id=result.request_id,
            title=f"[{environment}] 自动化执行失败 - {failed_case}",
            description=(
                "自动化测试执行过程中发现异常，请结合附件中的日志和元数据进一步定位。"
            ),
            repro_steps=[
                "进入本地测试工作台执行中心",
                "选择对应场景并触发自动化执行",
                "观察 pytest 输出与生成的执行产物",
            ],
            expected_result="自动化场景全部通过，页面或接口行为符合需求预期。",
            actual_result=result.summary or "执行失败，请查看附件。",
            attachments=attachments,
            yunxiao_fields={
                "environment": environment,
                "failedCount": str(result.failed),
                "requestId": result.request_id,
            },
            report_summary=result.summary,
        )
