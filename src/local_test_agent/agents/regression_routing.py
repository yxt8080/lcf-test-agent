from __future__ import annotations

from pydantic import BaseModel, Field

from local_test_agent.agents.base import BaseStructuredAgent
from local_test_agent.models import RegressionSuggestion, ScenarioDescriptor


class RegressionRoutingPayload(BaseModel):
    suggestions: list[RegressionSuggestion] = Field(default_factory=list)


class RegressionRoutingAgent(BaseStructuredAgent[RegressionRoutingPayload]):
    system_prompt = (
        "你是回归测试路由代理。请根据 bug 描述和候选场景，输出最值得执行的自动化场景。"
    )
    output_type = RegressionRoutingPayload

    def recommend(
        self,
        bug_description: str,
        candidate_scenarios: list[ScenarioDescriptor],
    ) -> list[RegressionSuggestion]:
        fallback = self._build_fallback(bug_description, candidate_scenarios)
        prompt = self.build_prompt(bug_description, candidate_scenarios)
        payload = self.run_structured(
            prompt,
            fallback,
            log_context={
                "candidate_count": len(candidate_scenarios),
                "bug_description_length": len(bug_description.strip()),
            },
        )
        return payload.suggestions

    def build_prompt(
        self,
        bug_description: str,
        candidate_scenarios: list[ScenarioDescriptor],
    ) -> str:
        return "\n".join(
            [
                f"Bug 描述: {bug_description}",
                "候选场景:",
                *[
                    f"- {item.scenario_id} | {item.title} | 模块: {item.module} | 步骤: {'; '.join(item.steps)}"
                    for item in candidate_scenarios
                ],
            ]
        )

    def _build_fallback(
        self,
        bug_description: str,
        candidate_scenarios: list[ScenarioDescriptor],
    ) -> RegressionRoutingPayload:
        bug_terms = {term.lower() for term in bug_description.replace("，", " ").split() if term.strip()}
        ranked: list[RegressionSuggestion] = []
        for scenario in candidate_scenarios:
            scenario_text = " ".join(
                [
                    scenario.title,
                    scenario.module,
                    " ".join(scenario.tags),
                    " ".join(scenario.steps),
                    " ".join(scenario.assertions),
                ]
            ).lower()
            matches = sum(1 for term in bug_terms if term and term in scenario_text)
            score = min(1.0, matches / max(len(bug_terms), 1))
            if matches == 0 and candidate_scenarios:
                score = 0.2
            ranked.append(
                RegressionSuggestion(
                    scenario_id=scenario.scenario_id,
                    title=scenario.title,
                    module=scenario.module,
                    priority="高" if score >= 0.6 else "中",
                    rationale="命中 bug 描述关键词并覆盖相同模块。" if matches else "作为相邻模块回归补充场景。",
                    recommended_scope="优先执行当前场景，再覆盖同模块的新增/编辑/提交流程。",
                    score=score,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return RegressionRoutingPayload(suggestions=ranked[:5])
