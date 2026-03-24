from __future__ import annotations

import re
from itertools import islice

from pydantic import BaseModel, Field

from local_test_agent.agents.base import BaseStructuredAgent
from local_test_agent.models import (
    AnalysisFeature,
    CheckPoint,
    OpenQuestion,
    RequirementInput,
    RequirementRefinementRound,
    RiskItem,
    ScenarioDetailLevel,
    ScenarioDescriptor,
    ScenarioKind,
    ScenarioPriority,
    ScenarioType,
    TestAnalysisResult,
    TestPath,
)


class RequirementAnalysisPayload(BaseModel):
    requirement_id: str
    features: list[AnalysisFeature] = Field(default_factory=list)
    test_paths: list[TestPath] = Field(default_factory=list)
    scenarios: list[ScenarioDescriptor] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    summary: str = ""

    def to_result(self) -> TestAnalysisResult:
        return TestAnalysisResult(
            requirement_id=self.requirement_id,
            features=self.features,
            test_paths=self.test_paths,
            scenarios=self.scenarios,
            risks=self.risks,
            open_questions=self.open_questions,
            summary=self.summary,
        )


class RequirementAnalysisAgent(BaseStructuredAgent[RequirementAnalysisPayload]):
    system_prompt = (
        "你是测试分析代理，负责把需求材料提炼成稳定可复用的结构化测试分析。\n"
        "你的核心职责是提炼高质量的业务功能点、测试边界、业务风险、业务待确认项和总体摘要，不要把回答退化成泛泛总结。\n"
        "输出要求：\n"
        "1. requirement_id 必须保留输入需求的唯一标识。\n"
        "2. features 必须非空，优先输出 2-6 个可测试的独立业务点，不能只重复章节标题。\n"
        "3. risks 只保留真正影响测试设计或测试稳定性的业务风险，不要写成实现建议或需求吐槽。\n"
        "4. open_questions 只保留业务规则类待确认项，必须直接影响测试范围、业务断言口径或业务规则歧义。\n"
        "5. summary 只能做总体总结，不能代替 features / risks / open_questions。\n"
        "6. scenarios 和 test_paths 允许留空，系统会按本地覆盖范围规则重新生成，不要在这里展开冗长场景明细。\n"
        "7. 若信息不足，优先补 open_questions，不要把 features 留空。\n"
        "8. 禁止把接口地址、请求参数格式、响应格式、Swagger/OpenAPI 地址、联调环境信息、测试账号准备方式写入 open_questions。\n"
        "9. 若页面已给出可观察行为、提示文案、跳转结果、状态变化，请直接沉淀到 features / risks，不要继续追问实现细节。"
    )
    output_type = RequirementAnalysisPayload

    def analyze(
        self,
        requirement: RequirementInput,
        *,
        refinement_history: list[RequirementRefinementRound] | None = None,
        latest_user_input: str = "",
    ) -> TestAnalysisResult:
        fallback = self._build_fallback(
            requirement,
            refinement_history=refinement_history,
            latest_user_input=latest_user_input,
        )
        prompt = self.build_prompt(
            requirement,
            refinement_history=refinement_history,
            latest_user_input=latest_user_input,
        )
        payload = self.run_structured(
            prompt,
            fallback,
            log_context={
                "requirement_id": requirement.id,
                "scenario_detail_level": requirement.scenario_detail_level.value,
                "refinement_round": len(refinement_history or []),
                "has_latest_user_input": bool(latest_user_input.strip()),
            },
        )
        normalized_payload = self._normalize_payload(requirement, payload)
        return normalized_payload.to_result()

    def validate_output(self, output: RequirementAnalysisPayload) -> tuple[bool, str]:
        # 需求分析是后续自动化、回归和交接的上游输入，若模型连功能点都没提炼出来，
        # 页面虽然可能拿到一段摘要，但本地无法稳定展开可用场景，因此直接回退到规则结果。
        if not output.features:
            return False, "requirement_analysis_missing_features"
        return super().validate_output(output)

    def build_prompt(
        self,
        requirement: RequirementInput,
        *,
        refinement_history: list[RequirementRefinementRound] | None = None,
        latest_user_input: str = "",
    ) -> str:
        refinement_history = refinement_history or []
        history_lines = ["历史补充说明:"]
        if refinement_history:
            history_lines.extend(
                [
                    f"- 第 {item.round_index} 轮：{item.user_input or '初次分析'}"
                    for item in refinement_history
                ]
            )
        else:
            history_lines.append("- 暂无")
        return "\n".join(
            [
                "任务目标:",
                "- 提炼功能点、风险点、待确认项和总体摘要。",
                "- 不必展开详细测试场景，场景会由系统按覆盖范围重建。",
                "",
                "上下文使用优先级:",
                "- 本轮用户补充优先级最高，若与旧内容冲突，以本轮补充为准。",
                "- 历史补充说明次之，用于继承已确认的上下文。",
                "- 需求正文是基础事实来源。",
                "- 补充说明用于补齐背景和测试关注点。",
                "",
                "输出约束:",
                "- features 必须非空，每项都要是可直接进入测试设计的业务点。",
                "- risks 只保留测试稳定性或业务高风险，不要写成产品待办或开发改造建议。",
                "- open_questions 只保留业务规则类问题，不要追问接口地址、请求体、响应体、Swagger/OpenAPI、联调环境、测试账号。",
                "- 如果信息不足，请在 open_questions 中提出，不要把结构化字段留空。",
                "- 若文档已明确提示文案、跳转页、状态变化、成功失败结果，请直接作为测试依据，不要继续追问实现细节。",
                "- 可保留示例：角色权限未明确、失败次数是否累计、成功后是否按角色跳转不同首页。",
                "- 禁止示例：登录接口 URL、请求 body 结构、返回 code 字段定义。",
                "",
                f"需求标题: {requirement.title}",
                f"需求来源: {requirement.source}",
                f"场景覆盖范围: {self._detail_label(requirement.scenario_detail_level)}",
                self._detail_instruction(requirement.scenario_detail_level),
                f"补充说明: {requirement.notes or '无'}",
                "需求正文:",
                requirement.markdown_content,
                "",
                "参考素材路径（仅供记录，当前模型未直接读取图片内容）:",
                *[f"- {path}" for path in requirement.image_paths],
                "",
                *history_lines,
                "",
                f"本轮用户补充: {latest_user_input or '无'}",
            ]
        )

    def _build_fallback(
        self,
        requirement: RequirementInput,
        *,
        refinement_history: list[RequirementRefinementRound] | None = None,
        latest_user_input: str = "",
    ) -> RequirementAnalysisPayload:
        analysis_source = self._build_analysis_source_text(
            requirement,
            refinement_history=refinement_history,
            latest_user_input=latest_user_input,
        )
        features = self._extract_features(analysis_source)
        scenarios = self._build_scenarios(requirement, features)
        test_paths = self._build_test_paths(scenarios)
        risks = self._extract_risks(analysis_source)
        open_questions = self._extract_open_questions(requirement, analysis_source)
        summary = (
            f"当前按{self._detail_label(requirement.scenario_detail_level)}识别 {len(features)} 个功能点、{len(scenarios)} 个测试场景。"
            "当前结果为规则模式输出，建议在开发完成后结合真实页面与接口再确认。"
        )
        return RequirementAnalysisPayload(
            requirement_id=requirement.id,
            features=features,
            test_paths=test_paths,
            scenarios=scenarios,
            risks=risks,
            open_questions=open_questions,
            summary=summary,
        )

    def _build_analysis_source_text(
        self,
        requirement: RequirementInput,
        *,
        refinement_history: list[RequirementRefinementRound] | None = None,
        latest_user_input: str = "",
    ) -> str:
        parts = [
            requirement.notes,
            requirement.markdown_content,
        ]
        refinement_history = refinement_history or []
        parts.extend(item.user_input for item in refinement_history if item.user_input)
        if latest_user_input:
            parts.append(latest_user_input)
        return "\n".join(item for item in parts if item)

    def _normalize_payload(
        self,
        requirement: RequirementInput,
        payload: RequirementAnalysisPayload,
    ) -> RequirementAnalysisPayload:
        normalized_features = self._normalize_features(requirement, payload.features)
        normalized_scenarios = self._build_scenarios(requirement, normalized_features)
        normalized_test_paths = self._build_test_paths(normalized_scenarios)
        normalized_open_questions = self._normalize_open_questions(payload.open_questions)
        summary = payload.summary.strip() or self._build_scope_summary(requirement, normalized_features, normalized_scenarios)
        return payload.model_copy(
            update={
                "features": normalized_features,
                "scenarios": normalized_scenarios,
                "test_paths": normalized_test_paths,
                "open_questions": normalized_open_questions,
                "summary": summary,
            }
        )

    def _extract_features(self, markdown_content: str) -> list[AnalysisFeature]:
        heading_lines = [
            line.strip("# ").strip()
            for line in markdown_content.splitlines()
            if line.strip().startswith("#")
        ]
        bullet_lines = [
            line.strip("- ").strip()
            for line in markdown_content.splitlines()
            if line.strip().startswith(("-", "*"))
        ]
        candidates = heading_lines or bullet_lines or self._fallback_sentences(markdown_content)
        features: list[AnalysisFeature] = []
        for feature_name in islice(candidates, 6):
            clean_name = feature_name[:60] or "未命名功能点"
            features.append(
                AnalysisFeature(
                    name=clean_name,
                    summary=f"围绕“{clean_name}”设计功能、数据流和异常路径测试。",
                    source_excerpt=clean_name,
                )
            )
        if not features:
            features.append(
                AnalysisFeature(
                    name="默认功能点",
                    summary="需求文本信息不足，需补充页面和接口细节后再细化。",
                    source_excerpt="",
                )
            )
        return features

    def _normalize_features(
        self,
        requirement: RequirementInput,
        features: list[AnalysisFeature],
    ) -> list[AnalysisFeature]:
        fallback_features = self._extract_features(requirement.markdown_content or requirement.notes)
        candidates = features or fallback_features
        max_features = {
            ScenarioDetailLevel.BRIEF: 3,
            ScenarioDetailLevel.STANDARD: 4,
            ScenarioDetailLevel.DETAILED: 6,
        }[requirement.scenario_detail_level]
        ranked_candidates = sorted(
            enumerate(candidates),
            key=lambda item: (
                -self._score_feature_priority(item[1]),
                item[0],
            ),
        )
        normalized: list[AnalysisFeature] = []
        for _, item in ranked_candidates[:max_features]:
            summary = item.summary.strip() or f"围绕“{item.name.strip() or '未命名功能点'}”验证核心业务行为、结果反馈和异常拦截。"
            source_excerpt = item.source_excerpt.strip() or item.name.strip() or summary[:60]
            normalized.append(
                item.model_copy(
                    update={
                        "summary": summary,
                        "source_excerpt": source_excerpt,
                    }
                )
            )
        return normalized

    @staticmethod
    def _score_feature_priority(feature: AnalysisFeature) -> int:
        combined_text = " ".join(
            part.strip()
            for part in (feature.name, feature.summary, feature.source_excerpt)
            if part and part.strip()
        )

        # 需求分析页的 brief/standard 模式需要优先保住业务主链路，因此这里显式压低
        # “页面元素展示/纯输入校验”类特征，避免它们把登录结果、状态变化等核心业务点挤掉。
        score = 0
        high_priority_keywords = (
            "结果",
            "成功",
            "失败",
            "完成",
            "提交",
            "交互",
            "流程",
            "跳转",
            "状态",
            "会话",
            "锁定",
            "认证",
            "异常",
            "超时",
            "断开",
            "服务异常",
        )
        validation_keywords = (
            "校验",
            "验证",
            "格式",
            "必填",
            "长度",
            "账号输入",
            "密码输入",
        )
        peripheral_keywords = (
            "页面元素",
            "元素展示",
            "占位提示",
            "输入框",
            "按钮文案",
            "掩码显示",
            "展示",
        )
        if any(keyword in combined_text for keyword in high_priority_keywords):
            score += 100
        if any(keyword in combined_text for keyword in validation_keywords):
            score += 25
        if any(keyword in combined_text for keyword in peripheral_keywords):
            score -= 45
        return score

    def _normalize_open_questions(self, open_questions: list[OpenQuestion]) -> list[OpenQuestion]:
        normalized: list[OpenQuestion] = []
        seen_questions: set[str] = set()
        for item in open_questions:
            question = item.question.strip()
            reason = item.reason.strip()
            if not question:
                continue
            if self._is_contract_detail_question(question, reason):
                continue
            if self._classify_open_question(question, reason) is None:
                continue
            if question in seen_questions:
                continue
            seen_questions.add(question)
            normalized.append(
                item.model_copy(
                    update={
                        "question": question,
                        "reason": reason or "该问题会直接影响测试范围或业务断言口径。",
                    }
                )
            )
            if len(normalized) >= 3:
                break
        return normalized

    @staticmethod
    def _is_contract_detail_question(question: str, reason: str) -> bool:
        combined_text = f"{question} {reason}".lower()
        blocked_keywords = (
            "接口地址",
            "接口 url",
            "api url",
            "swagger",
            "openapi",
            "请求参数",
            "请求体",
            "request body",
            "响应格式",
            "响应体",
            "response body",
            "header",
            "headers",
            "token字段",
            "联调环境",
            "测试账号",
            "账号准备",
        )
        return any(keyword in combined_text for keyword in blocked_keywords)

    @staticmethod
    def _classify_open_question(question: str, reason: str) -> str | None:
        combined_text = f"{question} {reason}"
        scope_keywords = ("是否支持", "是否需要", "是否覆盖", "范围", "角色", "权限", "兼容", "终端", "浏览器")
        assertion_keywords = ("提示", "文案", "错误码", "跳转", "成功后", "失败后", "状态", "保留", "清空", "展示")
        rule_keywords = ("规则", "条件", "累计", "次数", "时机", "顺序", "口径", "锁定", "状态流转", "何时", "未明确", "待定")
        if any(keyword in combined_text for keyword in scope_keywords):
            return "scope"
        if any(keyword in combined_text for keyword in assertion_keywords):
            return "assertion"
        if any(keyword in combined_text for keyword in rule_keywords):
            return "rule"
        return None

    def _build_test_paths(self, scenarios: list[ScenarioDescriptor]) -> list[TestPath]:
        main_flow_ids = [item.scenario_id for item in scenarios if item.scenario_kind is ScenarioKind.MAIN_FLOW]
        non_main_flow_ids = [item.scenario_id for item in scenarios if item.scenario_kind is not ScenarioKind.MAIN_FLOW]
        return [
            TestPath(
                name="主流程验证",
                objective="覆盖需求中的核心业务路径和正向操作。",
                scenario_ids=main_flow_ids[:3],
            ),
            TestPath(
                name="异常与边界验证",
                objective="覆盖关键异常、边界、权限和状态流转场景。",
                scenario_ids=non_main_flow_ids,
            ),
        ]

    def _build_scope_summary(
        self,
        requirement: RequirementInput,
        features: list[AnalysisFeature],
        scenarios: list[ScenarioDescriptor],
    ) -> str:
        return (
            f"当前按{self._detail_label(requirement.scenario_detail_level)}识别 {len(features)} 个功能点、"
            f"{len(scenarios)} 个测试场景。"
        )

    def _build_scenarios(
        self,
        requirement: RequirementInput,
        features: list[AnalysisFeature],
    ) -> list[ScenarioDescriptor]:
        scenarios: list[ScenarioDescriptor] = []
        base_prefix = requirement.id[:8].upper()
        index = 1
        for feature_index, feature in enumerate(features, start=1):
            for blueprint in self._build_feature_scenario_blueprints(
                requirement,
                feature,
                feature_index=feature_index,
                total_features=len(features),
            ):
                module = feature.name.split()[0]
                scenario_id = f"SCN-{base_prefix}-{index:02d}"
                index += 1
                automation_type = ScenarioType.API if "接口" in feature.name else ScenarioType.UI
                steps = blueprint["steps"]
                assertions = blueprint["assertions"]
                scenarios.append(
                    ScenarioDescriptor(
                        scenario_id=scenario_id,
                        title=blueprint["title"],
                        summary=blueprint["summary"],
                        priority=self._resolve_priority(feature.name, blueprint["title"]),
                        scenario_kind=blueprint["kind"],
                        module=module,
                        automation_type=automation_type,
                        tags=[
                            module,
                            automation_type.value,
                            "需求分析",
                            requirement.scenario_detail_level.value,
                            blueprint["kind"].value,
                        ],
                        preconditions=["测试环境已部署最新需求代码", "已准备可用测试账号和测试数据"],
                        steps=steps,
                        assertions=assertions,
                        related_pages=[feature.name],
                        checkpoints=[
                            CheckPoint(title="核心路径", detail="验证主流程是否可达且结果正确"),
                            CheckPoint(title="失败提示", detail="验证异常或校验失败时的提示信息"),
                        ],
                        test_selector="tests/test_generated_placeholder.py::test_generated_placeholder",
                    )
                )
        return self._cap_scenarios(requirement, scenarios)

    def _build_feature_scenario_blueprints(
        self,
        requirement: RequirementInput,
        feature: AnalysisFeature,
        *,
        feature_index: int,
        total_features: int,
    ) -> list[dict[str, object]]:
        feature_name = feature.name
        base_steps = [
            f"进入 {feature_name} 对应入口",
            "按需求说明完成核心操作",
            "提交后观察页面提示或接口返回",
        ]
        base_assertions = [
            "页面展示与需求一致",
            "关键字段保存或返回成功",
            "异常场景给出明确提示",
        ]
        blueprints: list[dict[str, object]] = [
            {
                "title": f"{feature_name}主流程验证",
                "summary": f"验证 {feature_name} 的核心主流程是否可正常完成，并正确返回结果或提示。",
                "kind": ScenarioKind.MAIN_FLOW,
                "steps": base_steps,
                "assertions": base_assertions,
            }
        ]

        if requirement.scenario_detail_level is ScenarioDetailLevel.BRIEF:
            return blueprints

        high_risk_feature = any(keyword in feature_name for keyword in ("审批", "支付", "登录", "权限", "接口"))
        if requirement.scenario_detail_level is ScenarioDetailLevel.STANDARD:
            should_add_exception = high_risk_feature or feature_index <= min(2, total_features)
            if should_add_exception:
                blueprints.append(
                    {
                        "title": f"{feature_name}关键异常验证",
                        "summary": f"验证 {feature_name} 在关键异常或校验失败场景下的提示和拦截是否正确。",
                        "kind": ScenarioKind.KEY_EXCEPTION,
                        "steps": [
                            f"进入 {feature_name} 对应入口",
                            "构造关键校验失败或异常数据",
                            "提交后观察拦截和错误提示",
                        ],
                        "assertions": [
                            "操作被正确拦截",
                            "错误提示清晰且与规则一致",
                            "未产生错误落库或错误状态变更",
                        ],
                    }
                )
            return blueprints

        blueprints.extend(
            [
                {
                    "title": f"{feature_name}校验失败提示",
                    "summary": f"验证 {feature_name} 在参数缺失、格式错误等校验失败时的提示是否准确。",
                    "kind": ScenarioKind.BOUNDARY,
                    "steps": [
                        f"进入 {feature_name} 对应入口",
                        "输入不完整或不合法的数据",
                        "提交后观察页面或接口错误提示",
                    ],
                    "assertions": [
                        "校验规则被触发",
                        "提示文案准确可理解",
                        "数据未被错误提交",
                    ],
                },
                {
                    "title": f"{feature_name}状态切换与权限边界",
                    "summary": f"验证 {feature_name} 在状态变化、角色权限或边界操作下的处理是否符合预期。",
                    "kind": (
                        ScenarioKind.PERMISSION
                        if any(keyword in feature_name for keyword in ("权限", "角色", "登录"))
                        else ScenarioKind.STATE_TRANSITION
                    ),
                    "steps": [
                        f"进入 {feature_name} 对应入口",
                        "使用边界状态或受限角色执行操作",
                        "观察状态变更、按钮可用性和最终结果",
                    ],
                    "assertions": [
                        "状态流转符合业务规则",
                        "权限限制生效且无越权",
                        "界面反馈或接口返回清晰",
                    ],
                },
            ]
        )
        return blueprints

    def _cap_scenarios(
        self,
        requirement: RequirementInput,
        scenarios: list[ScenarioDescriptor],
    ) -> list[ScenarioDescriptor]:
        max_scenarios = {
            ScenarioDetailLevel.BRIEF: 4,
            ScenarioDetailLevel.STANDARD: 8,
            ScenarioDetailLevel.DETAILED: 15,
        }[requirement.scenario_detail_level]
        kind_order = {
            ScenarioKind.MAIN_FLOW: 0,
            ScenarioKind.KEY_EXCEPTION: 1,
            ScenarioKind.BOUNDARY: 2,
            ScenarioKind.PERMISSION: 3,
            ScenarioKind.STATE_TRANSITION: 4,
        }
        return sorted(
            scenarios,
            key=lambda item: (kind_order.get(item.scenario_kind, 99), item.scenario_id),
        )[:max_scenarios]

    def _resolve_priority(self, feature_name: str, scenario_title: str) -> ScenarioPriority:
        combined_text = f"{feature_name} {scenario_title}"
        if any(keyword in combined_text for keyword in ("登录", "支付", "审批", "提交", "主流程")):
            return ScenarioPriority.P0
        if any(keyword in combined_text for keyword in ("状态", "权限", "核心", "关键")):
            return ScenarioPriority.P1
        if any(keyword in combined_text for keyword in ("校验", "异常", "边界", "提示")):
            return ScenarioPriority.P2
        return ScenarioPriority.P3

    @staticmethod
    def _detail_label(detail_level: ScenarioDetailLevel) -> str:
        return {
            ScenarioDetailLevel.BRIEF: "核心主链路",
            ScenarioDetailLevel.STANDARD: "标准测试",
            ScenarioDetailLevel.DETAILED: "完整覆盖",
        }[detail_level]

    @staticmethod
    def _detail_instruction(detail_level: ScenarioDetailLevel) -> str:
        return {
            ScenarioDetailLevel.BRIEF: "覆盖规则: 只输出主流程场景，不展开判空、边界和权限类场景。",
            ScenarioDetailLevel.STANDARD: "覆盖规则: 输出主流程和关键异常场景，优先保留核心提测范围。",
            ScenarioDetailLevel.DETAILED: "覆盖规则: 输出主流程、异常、边界、权限和状态流转等完整覆盖场景。",
        }[detail_level]

    def _extract_risks(self, markdown_content: str) -> list[RiskItem]:
        rules = {
            "权限": ("高", "涉及角色和数据范围，容易出现越权。"),
            "导入": ("中", "批量导入常出现格式和脏数据问题。"),
            "导出": ("中", "导出字段、权限和性能容易偏差。"),
            "支付": ("高", "金额和状态流转错误会直接影响业务结果。"),
            "审批": ("高", "状态迁移和回退规则复杂，需重点覆盖。"),
        }
        risks: list[RiskItem] = []
        for keyword, (level, impact) in rules.items():
            if keyword in markdown_content:
                risks.append(
                    RiskItem(
                        title=f"{keyword}相关风险",
                        level=level,
                        impact=impact,
                        mitigation="补充角色矩阵、异常数据与跨状态流转用例。",
                    )
                )
        if not risks:
            risks.append(
                RiskItem(
                    title="联调阶段风险",
                    level="中",
                    impact="前后端接口契约变化可能导致页面或接口断言失效。",
                    mitigation="开发部署测试环境后，先做页面与接口基线核对。",
                )
            )
        return risks

    def _extract_open_questions(
        self,
        requirement: RequirementInput,
        analysis_source: str,
    ) -> list[OpenQuestion]:
        questions: list[OpenQuestion] = []
        if requirement.image_paths:
            questions.append(
                OpenQuestion(
                    question="截图对应页面是否为最终交互稿？",
                    reason="页面布局和字段位置变化会直接影响 UI 自动化定位。",
                )
            )
        if re.search(r"(角色未定|角色待定|权限待定)", analysis_source, re.IGNORECASE):
            questions.append(
                OpenQuestion(
                    question="角色权限范围最终是否已确认？",
                    reason="角色边界会直接影响测试覆盖范围和越权断言口径。",
                )
            )
        if re.search(r"(规则未定|规则待定|口径待定)", analysis_source, re.IGNORECASE):
            questions.append(
                OpenQuestion(
                    question="相关业务规则的最终口径是否已经确认？",
                    reason="规则口径不一致会导致断言结论和回归范围偏差。",
                )
            )
        if "待定" in analysis_source or "TODO" in analysis_source.upper() or "TBD" in analysis_source.upper():
            questions.append(
                OpenQuestion(
                    question="需求文档中的待定项最终是否已确认？",
                    reason="未确认的规则容易造成错误断言或重复返工。",
                )
            )
        return questions

    @staticmethod
    def _fallback_sentences(markdown_content: str) -> list[str]:
        return [line.strip() for line in markdown_content.splitlines() if line.strip()][:5]
