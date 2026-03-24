from __future__ import annotations

from pydantic import BaseModel, Field

from local_test_agent.agents.base import BaseStructuredAgent
from local_test_agent.models import (
    CodegenTaskPack,
    ScenarioDescriptor,
    ScenarioPriority,
    ScenarioType,
    TestAnalysisResult,
)


class AutomationPlanningPayload(BaseModel):
    requirement_id: str
    target_type: ScenarioType
    context_summary: str
    scenarios: list[ScenarioDescriptor] = Field(default_factory=list)
    coding_prompt: str
    acceptance_checks: list[str] = Field(default_factory=list)
    file_naming_rules: list[str] = Field(default_factory=list)

    def to_pack(self) -> CodegenTaskPack:
        return CodegenTaskPack(**self.model_dump())


class AutomationPlanningAgent(BaseStructuredAgent[AutomationPlanningPayload]):
    system_prompt = (
        "你是自动化测试设计代理。请基于测试分析结果、页面说明和 OpenAPI 摘要，"
        "产出可直接交给 Codex 或 Claude Code 的自动化开发任务包。"
        "如果目标包含 API 自动化但缺少 OpenAPI/接口摘要，请明确标记为自动化前置资料缺失，"
        "不要反向要求需求分析节点补接口契约。"
    )
    output_type = AutomationPlanningPayload

    def plan(
        self,
        analysis: TestAnalysisResult,
        page_summary: str,
        openapi_summary: dict,
        target_type: ScenarioType,
    ) -> CodegenTaskPack:
        fallback = self._build_fallback(analysis, page_summary, openapi_summary, target_type)
        prompt = self.build_prompt(analysis, page_summary, openapi_summary, target_type)
        payload = self.run_structured(
            prompt,
            fallback,
            log_context={
                "requirement_id": analysis.requirement_id,
                "target_type": target_type.value,
                "scenario_count": len(analysis.scenarios),
                "openapi_operation_count": openapi_summary.get("operation_count", 0),
            },
        )
        return payload.to_pack()

    def build_prompt(
        self,
        analysis: TestAnalysisResult,
        page_summary: str,
        openapi_summary: dict,
        target_type: ScenarioType,
    ) -> str:
        sorted_scenarios = self._sort_scenarios_by_priority(analysis.scenarios)
        openapi_note = self._build_openapi_prerequisite_note(target_type, openapi_summary)
        return "\n".join(
            [
                f"目标类型: {target_type.value}",
                f"自动化前置资料状态: {openapi_note or '资料齐备，可直接细化实现。'}",
                f"需求摘要: {analysis.summary}",
                "页面说明:",
                page_summary or "无",
                "OpenAPI 摘要:",
                str(openapi_summary),
                "测试场景:",
                *[
                    f"- {item.priority.value} {item.scenario_id} {item.title} | 摘要: {item.summary} | 模块: {item.module} | 断言: {'; '.join(item.assertions[:2])}"
                    for item in sorted_scenarios
                ],
            ]
        )

    def _build_fallback(
        self,
        analysis: TestAnalysisResult,
        page_summary: str,
        openapi_summary: dict,
        target_type: ScenarioType,
    ) -> AutomationPlanningPayload:
        scenarios = [
            item
            for item in analysis.scenarios
            if target_type is ScenarioType.MIXED or item.automation_type in {target_type, ScenarioType.MIXED}
        ] or analysis.scenarios
        scenarios = self._sort_scenarios_by_priority(scenarios)
        operation_lines = [
            f"{item['method']} {item['path']} ({item['operation_id']})"
            for item in openapi_summary.get("operations", [])[:8]
        ]
        openapi_note = self._build_openapi_prerequisite_note(target_type, openapi_summary)
        coding_prompt = "\n".join(
            [
                "你现在是测试自动化开发助手，请基于以下上下文编写测试代码。",
                f"目标类型：{target_type.value}",
                f"需求摘要：{analysis.summary}",
                f"页面说明：{page_summary or '无'}",
                f"自动化前置资料：{openapi_note or '资料齐备，可直接展开接口断言。'}",
                "优先覆盖场景：",
                *[f"- {item.priority.value} {item.scenario_id} {item.title} | {item.summary}" for item in scenarios],
                "接口摘要：",
                *([f"- {line}" for line in operation_lines] or ["- 无接口摘要"]),
                "实现要求：",
                "- 使用 pytest 组织测试",
                "- UI 自动化使用 Playwright Python",
                "- API 自动化使用 httpx",
                "- 断言需覆盖主流程、关键返回字段和错误提示",
                "- 输出代码时补充必要中文注释，说明业务意图和约束原因",
            ]
        )
        return AutomationPlanningPayload(
            requirement_id=analysis.requirement_id,
            target_type=target_type,
            context_summary=self._build_context_summary(
                page_summary=page_summary,
                openapi_summary=openapi_summary,
                target_type=target_type,
                scenarios=scenarios,
            ),
            scenarios=scenarios,
            coding_prompt=coding_prompt,
            acceptance_checks=[
                "存在成功路径断言",
                "存在至少一个异常路径断言",
                "测试数据准备步骤明确",
                "代码中包含可维护的页面对象或接口客户端封装",
            ],
            file_naming_rules=[
                "UI 测试放在 tests/ui/test_<module>.py",
                "API 测试放在 tests/api/test_<module>_api.py",
                "公共能力放在 tests/support/",
            ],
        )

    @staticmethod
    def _sort_scenarios_by_priority(scenarios: list[ScenarioDescriptor]) -> list[ScenarioDescriptor]:
        order = {
            ScenarioPriority.P0: 0,
            ScenarioPriority.P1: 1,
            ScenarioPriority.P2: 2,
            ScenarioPriority.P3: 3,
        }
        return sorted(scenarios, key=lambda item: (order.get(item.priority, 99), item.scenario_id))

    def _build_context_summary(
        self,
        *,
        page_summary: str,
        openapi_summary: dict,
        target_type: ScenarioType,
        scenarios: list[ScenarioDescriptor],
    ) -> str:
        summary = (
            f"页面说明长度 {len(page_summary)}，OpenAPI 接口数 {openapi_summary.get('operation_count', 0)}。"
            f" 当前测试场景已按优先级排序，最高优先级为 {scenarios[0].priority.value if scenarios else 'P2'}。"
        )
        prerequisite_note = self._build_openapi_prerequisite_note(target_type, openapi_summary)
        if not prerequisite_note:
            return summary
        # 接口契约缺口只在自动化设计阶段提示，避免污染需求分析里的业务待确认项。
        return f"{summary} {prerequisite_note}"

    @staticmethod
    def _build_openapi_prerequisite_note(target_type: ScenarioType, openapi_summary: dict) -> str:
        needs_api_contract = target_type in {ScenarioType.API, ScenarioType.MIXED}
        if not needs_api_contract or openapi_summary.get("operation_count", 0) > 0:
            return ""
        return "自动化前置资料缺失：当前未提供 OpenAPI/接口摘要，API 断言与客户端封装需在补齐契约后再细化。"
