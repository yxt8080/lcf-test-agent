from __future__ import annotations

import sqlite3

import pytest

from local_test_agent.adapters.llm import LLMAdapter
from local_test_agent.agents.requirement_analysis import RequirementAnalysisAgent, RequirementAnalysisPayload
from local_test_agent.config import LLMSettings
from local_test_agent.bootstrap import build_controller
from local_test_agent.models import (
    AnalysisFeature,
    BusinessCategory,
    BusinessSubcategory,
    OpenQuestion,
    ScenarioDescriptor,
    ScenarioDetailLevel,
    ScenarioHandoffStatus,
    ScenarioKind,
    ScenarioPriority,
    ScenarioType,
)
from local_test_agent.store.llm_log_store import LLMLogStore


def _default_statuses(analysis) -> dict[str, str]:
    return {
        item.scenario_id: ScenarioHandoffStatus.AUTOMATION.value
        for item in analysis.scenarios
    }


def _confirm_requirement_record(controller, requirement, scenario_statuses: dict[str, str] | None = None):
    draft = controller.start_requirement_analysis(requirement)
    assert draft.latest_analysis is not None
    analysis = draft.latest_analysis
    controller.save_requirement_draft_handoff(
        scenario_statuses=scenario_statuses or _default_statuses(analysis)
    )
    record = controller.confirm_requirement_draft()
    return analysis, record


def test_requirement_analysis_stays_in_draft_until_confirmed(controller):
    requirement = controller.create_requirement_input(
        title="订单审批流程",
        markdown_content="# 订单审批\n- 需要支持审批通过和驳回\n- 涉及权限校验",
        image_paths=["/tmp/mock.png"],
        source="prd",
        notes="接口文档稍后补充",
    )

    draft = controller.start_requirement_analysis(requirement)

    assert draft.requirement.id == requirement.id
    assert draft.latest_analysis is not None
    assert draft.latest_analysis.features
    assert draft.latest_analysis.scenarios
    assert any("权限" in risk.title for risk in draft.latest_analysis.risks)
    assert controller.list_requirement_records() == []
    assert controller.get_active_requirement_draft() is not None


def test_requirement_analysis_detail_levels_control_scenario_count_and_priority(controller):
    markdown = "# 用户登录\n## 登录成功\n## 登录失败\n## 找回密码\n## 账号锁定"

    brief_requirement = controller.create_requirement_input(
        title="细致度简要",
        markdown_content=markdown,
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.BRIEF.value,
    )
    standard_requirement = controller.create_requirement_input(
        title="细致度标准",
        markdown_content=markdown,
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.STANDARD.value,
    )
    detailed_requirement = controller.create_requirement_input(
        title="细致度细致",
        markdown_content=markdown,
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.DETAILED.value,
    )

    brief = controller.start_requirement_analysis(brief_requirement).latest_analysis
    standard = controller.start_requirement_analysis(standard_requirement).latest_analysis
    detailed = controller.start_requirement_analysis(detailed_requirement).latest_analysis

    assert brief is not None and standard is not None and detailed is not None
    assert 3 <= len(brief.scenarios) <= 4
    assert 5 <= len(standard.scenarios) <= 8
    assert 8 <= len(detailed.scenarios) <= 15
    assert all(item.scenario_kind is ScenarioKind.MAIN_FLOW for item in brief.scenarios)
    assert any(item.scenario_kind is ScenarioKind.KEY_EXCEPTION for item in standard.scenarios)
    assert any(item.scenario_kind in {ScenarioKind.BOUNDARY, ScenarioKind.PERMISSION, ScenarioKind.STATE_TRANSITION} for item in detailed.scenarios)
    assert all(item.priority in {ScenarioPriority.P0, ScenarioPriority.P1, ScenarioPriority.P2, ScenarioPriority.P3} for item in detailed.scenarios)
    assert all(item.summary for item in detailed.scenarios)


def test_legacy_scenario_descriptor_backfills_summary_and_priority():
    scenario = ScenarioDescriptor.model_validate(
        {
            "scenario_id": "SCN-LEGACY-01",
            "title": "历史主流程",
            "module": "登录模块",
            "steps": ["打开登录页并输入账号密码"],
            "assertions": ["登录成功后跳转到首页"],
        }
    )

    assert scenario.priority == ScenarioPriority.P2
    assert "历史主流程" in scenario.summary
    assert "打开登录页并输入账号密码" in scenario.summary


def test_requirement_refine_updates_draft_without_creating_record(controller):
    requirement = controller.create_requirement_input(
        title="用户审批",
        markdown_content="# 用户审批\n## 审批通过\n## 审批驳回",
        image_paths=[],
        source="prd",
        notes="",
    )
    initial_draft = controller.start_requirement_analysis(requirement)
    refined_requirement = controller.create_requirement_input(
        title="用户审批",
        markdown_content="# 用户审批\n## 审批通过\n## 审批驳回\n## 越权校验",
        image_paths=[],
        source="prd",
        notes="增加权限风险",
        requirement_id=initial_draft.requirement.id,
        created_at=initial_draft.requirement.created_at,
    )

    refined_draft = controller.refine_requirement_analysis(
        requirement=refined_requirement,
        user_input="补充越权校验和角色矩阵要求",
    )

    assert refined_draft.latest_analysis is not None
    assert len(refined_draft.refinement_history) == 2
    assert "本轮变化" in refined_draft.refinement_history[-1].change_summary
    assert refined_draft.handoff_confirmed is False
    assert controller.list_requirement_records() == []


def test_requirement_analysis_normalizes_requirement_id_from_agent(controller, monkeypatch):
    requirement = controller.create_requirement_input(
        title="需求编号归一化",
        markdown_content="# 需求编号归一化\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )
    original_analyze = controller.requirement_agent.analyze

    def fake_analyze(payload, **kwargs):
        result = original_analyze(payload, **kwargs)
        return result.model_copy(update={"requirement_id": payload.title})

    monkeypatch.setattr(controller.requirement_agent, "analyze", fake_analyze)

    draft = controller.start_requirement_analysis(requirement)

    assert draft.latest_analysis is not None
    assert draft.latest_analysis.requirement_id == requirement.id


def test_requirement_analysis_falls_back_when_model_returns_summary_only(monkeypatch, tmp_path):
    class FakeRunResult:
        def __init__(self, output):
            self.output = output

    class FakeAgent:
        def __init__(self, _model, **_kwargs):
            pass

        def run_sync(self, _prompt):
            return FakeRunResult(
                RequirementAnalysisPayload(
                    requirement_id="summary-only",
                    summary="模型只返回了摘要，没有结构化测试内容。",
                )
            )

    class FakeOpenAIModel:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("local_test_agent.adapters.llm.Agent", FakeAgent)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIModel", FakeOpenAIModel)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIProvider", lambda **_kwargs: object())

    log_store = LLMLogStore(tmp_path / "llm_calls.log")
    agent = RequirementAnalysisAgent(
        LLMAdapter(
            LLMSettings(
                provider_model="openai:gpt-4.1-mini",
                api_key="demo-key",
                enable_live_llm=True,
            ),
            log_store=log_store,
        )
    )
    requirement = build_controller(tmp_path).create_requirement_input(
        title="登录页面",
        markdown_content="# 登录\n- 输入账号密码后提交",
        image_paths=[],
        source="prd",
        notes="",
    )

    result = agent.analyze(requirement)
    logs = log_store.read_recent(limit=1)

    assert result.features
    assert result.scenarios
    assert len(logs) == 1
    assert logs[0].used_fallback is True
    assert logs[0].fallback_reason == "requirement_analysis_missing_features"


def test_requirement_analysis_prompt_declares_priority_and_output_contract(tmp_path):
    agent = RequirementAnalysisAgent(LLMAdapter(LLMSettings()))
    requirement = build_controller(tmp_path).create_requirement_input(
        title="登录页面",
        markdown_content="# 登录\n- 输入账号密码后提交",
        image_paths=["/tmp/login.png"],
        source="prd",
        notes="补充系统背景",
        scenario_detail_level=ScenarioDetailLevel.BRIEF.value,
    )

    prompt = agent.build_prompt(
        requirement,
        refinement_history=[],
        latest_user_input="本轮补充新的锁定规则",
    )

    assert "本轮用户补充优先级最高" in prompt
    assert "features 必须非空" in prompt
    assert "场景会由系统按覆盖范围重建" in prompt
    assert "当前模型未直接读取图片内容" in prompt
    assert "不要追问接口地址、请求体、响应体、Swagger/OpenAPI" in prompt
    assert "禁止示例：登录接口 URL、请求 body 结构、返回 code 字段定义" in prompt


def test_requirement_analysis_accepts_feature_only_model_output_and_rebuilds_scenarios(monkeypatch, tmp_path):
    class FakeRunResult:
        def __init__(self, output):
            self.output = output

    class FakeAgent:
        def __init__(self, _model, **_kwargs):
            pass

        def run_sync(self, _prompt):
            return FakeRunResult(
                RequirementAnalysisPayload(
                    requirement_id="feature-only",
                    features=[
                        AnalysisFeature(
                            name="登录认证",
                            summary="围绕账号密码登录、锁定和异常提示做测试设计。",
                            source_excerpt="登录认证",
                        )
                    ],
                    summary="聚焦登录认证业务点。",
                )
            )

    class FakeOpenAIModel:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("local_test_agent.adapters.llm.Agent", FakeAgent)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIModel", FakeOpenAIModel)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIProvider", lambda **_kwargs: object())

    log_store = LLMLogStore(tmp_path / "llm_calls.log")
    agent = RequirementAnalysisAgent(
        LLMAdapter(
            LLMSettings(
                provider_model="openai:gpt-4.1-mini",
                api_key="demo-key",
                enable_live_llm=True,
            ),
            log_store=log_store,
        )
    )
    requirement = build_controller(tmp_path).create_requirement_input(
        title="登录页面",
        markdown_content="# 登录\n- 输入账号密码后提交",
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.STANDARD.value,
    )

    result = agent.analyze(requirement)
    logs = log_store.read_recent(limit=1)

    assert len(result.features) == 1
    assert result.scenarios
    assert result.test_paths
    assert len(logs) == 1
    assert logs[0].used_fallback is False
    assert logs[0].success is True


def test_requirement_analysis_prioritizes_business_core_features_in_brief_and_standard(monkeypatch, tmp_path):
    class FakeRunResult:
        def __init__(self, output):
            self.output = output

    class FakeAgent:
        def __init__(self, _model, **_kwargs):
            pass

        def run_sync(self, _prompt):
            return FakeRunResult(
                RequirementAnalysisPayload(
                    requirement_id="login-ranking",
                    features=[
                        AnalysisFeature(
                            name="登录页面元素展示",
                            summary="页面包含账号输入框、密码输入框和登录按钮。",
                            source_excerpt="登录页面元素展示",
                        ),
                        AnalysisFeature(
                            name="账号输入验证",
                            summary="账号必填且需要格式校验。",
                            source_excerpt="账号输入验证",
                        ),
                        AnalysisFeature(
                            name="密码输入验证",
                            summary="密码必填且需要长度校验。",
                            source_excerpt="密码输入验证",
                        ),
                        AnalysisFeature(
                            name="登录交互流程",
                            summary="提交后按钮进入登录中状态，不可重复点击。",
                            source_excerpt="登录交互流程",
                        ),
                        AnalysisFeature(
                            name="登录结果处理",
                            summary="成功后跳转首页，失败时停留当前页并保留账号。",
                            source_excerpt="登录结果处理",
                        ),
                        AnalysisFeature(
                            name="异常处理机制",
                            summary="网络异常、服务异常时给出明确提示。",
                            source_excerpt="异常处理机制",
                        ),
                    ],
                    summary="聚焦登录业务。",
                )
            )

    class FakeOpenAIModel:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("local_test_agent.adapters.llm.Agent", FakeAgent)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIModel", FakeOpenAIModel)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIProvider", lambda **_kwargs: object())

    agent = RequirementAnalysisAgent(
        LLMAdapter(
            LLMSettings(
                provider_model="openai:gpt-4.1-mini",
                api_key="demo-key",
                enable_live_llm=True,
            )
        )
    )
    brief_requirement = build_controller(tmp_path).create_requirement_input(
        title="登录简要排序",
        markdown_content="# 登录\n- 输入账号密码后提交",
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.BRIEF.value,
    )
    standard_requirement = build_controller(tmp_path).create_requirement_input(
        title="登录标准排序",
        markdown_content="# 登录\n- 输入账号密码后提交",
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.STANDARD.value,
    )

    brief_result = agent.analyze(brief_requirement)
    standard_result = agent.analyze(standard_requirement)

    brief_feature_names = [item.name for item in brief_result.features]
    standard_feature_names = [item.name for item in standard_result.features]

    assert brief_feature_names == ["登录交互流程", "登录结果处理", "异常处理机制"]
    assert "登录页面元素展示" not in standard_feature_names
    assert "登录结果处理" in standard_feature_names
    assert "登录交互流程" in standard_feature_names


def test_requirement_analysis_filters_contract_questions_and_caps_open_questions(monkeypatch, tmp_path):
    class FakeRunResult:
        def __init__(self, output):
            self.output = output

    class FakeAgent:
        def __init__(self, _model, **_kwargs):
            pass

        def run_sync(self, _prompt):
            return FakeRunResult(
                RequirementAnalysisPayload(
                    requirement_id="login-open-questions",
                    features=[
                        AnalysisFeature(
                            name="登录认证",
                            summary="验证登录成功、失败提示与账号状态变化。",
                            source_excerpt="登录认证",
                        )
                    ],
                    open_questions=[
                        OpenQuestion(
                            question="登录接口的具体地址、请求参数格式和响应格式是什么？",
                            reason="影响测试数据准备和断言验证",
                        ),
                        OpenQuestion(
                            question="登录失败次数是否按自然日清零，还是仅成功后重置？",
                            reason="会影响账号锁定规则的业务断言口径。",
                        ),
                        OpenQuestion(
                            question="登录成功后是否按角色跳转不同首页？",
                            reason="会改变主流程覆盖范围和成功断言。",
                        ),
                        OpenQuestion(
                            question="账号锁定期间是否允许通过忘记密码流程解除限制？",
                            reason="会影响异常场景范围和状态流转断言。",
                        ),
                        OpenQuestion(
                            question="错误码 1001 是否统一映射为“账号或密码错误”？",
                            reason="会影响失败提示文案和错误码断言口径。",
                        ),
                    ],
                    summary="聚焦登录认证业务点。",
                )
            )

    class FakeOpenAIModel:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("local_test_agent.adapters.llm.Agent", FakeAgent)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIModel", FakeOpenAIModel)
    monkeypatch.setattr("local_test_agent.adapters.llm.OpenAIProvider", lambda **_kwargs: object())

    agent = RequirementAnalysisAgent(
        LLMAdapter(
            LLMSettings(
                provider_model="openai:gpt-4.1-mini",
                api_key="demo-key",
                enable_live_llm=True,
            )
        )
    )
    requirement = build_controller(tmp_path).create_requirement_input(
        title="登录页面",
        markdown_content="# 登录\n- 输入账号密码后提交",
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.STANDARD.value,
    )

    result = agent.analyze(requirement)
    question_texts = [item.question for item in result.open_questions]

    assert len(question_texts) == 3
    assert all("接口" not in text or "错误码" in text for text in question_texts)
    assert all("请求参数" not in text for text in question_texts)
    assert all("响应格式" not in text for text in question_texts)
    assert "登录失败次数是否按自然日清零，还是仅成功后重置？" in question_texts
    assert "登录成功后是否按角色跳转不同首页？" in question_texts
    assert "账号锁定期间是否允许通过忘记密码流程解除限制？" in question_texts


def test_requirement_analysis_fallback_open_questions_only_keep_business_ambiguity(controller):
    requirement = controller.create_requirement_input(
        title="登录规则待定",
        markdown_content="# 登录\n- 角色未定\n- 规则待定\n- TODO: 锁定口径后补充",
        image_paths=[],
        source="prd",
        notes="当前需求还有角色未定和规则待定项。",
    )

    draft = controller.start_requirement_analysis(requirement)
    assert draft.latest_analysis is not None

    question_texts = [item.question for item in draft.latest_analysis.open_questions]

    assert "角色权限范围最终是否已确认？" in question_texts
    assert "相关业务规则的最终口径是否已经确认？" in question_texts
    assert "需求文档中的待定项最终是否已确认？" in question_texts
    assert all("Swagger" not in text for text in question_texts)
    assert all("OpenAPI" not in text for text in question_texts)


def test_requirement_handoff_filters_scenarios_for_automation(controller):
    requirement = controller.create_requirement_input(
        title="用户中心改造",
        markdown_content="# 用户中心\n## 新增用户\n## 角色授权\n## 停用用户",
        image_paths=[],
        source="prd",
        notes="",
    )
    draft = controller.start_requirement_analysis(requirement)
    analysis = draft.latest_analysis
    assert analysis is not None

    scenario_statuses = {
        item.scenario_id: ScenarioHandoffStatus.DEFERRED.value
        for item in analysis.scenarios
    }
    scenario_statuses[analysis.scenarios[0].scenario_id] = ScenarioHandoffStatus.REGRESSION_ONLY.value
    scenario_statuses[analysis.scenarios[1].scenario_id] = ScenarioHandoffStatus.AUTOMATION.value
    scenario_statuses[analysis.scenarios[2].scenario_id] = ScenarioHandoffStatus.DEFERRED.value
    scenario_statuses[analysis.scenarios[3].scenario_id] = ScenarioHandoffStatus.REGRESSION_ONLY.value

    handoff_draft = controller.save_requirement_draft_handoff(scenario_statuses=scenario_statuses)
    controller.confirm_requirement_draft()
    pack = controller.plan_automation(
        requirement_title="用户中心改造",
        page_summary="页面包含列表、弹窗和操作按钮。",
        openapi_path="",
        target_type=ScenarioType.MIXED.value,
    )

    assert handoff_draft.current_handoff is not None
    assert handoff_draft.current_handoff.selected_scenario_ids == [analysis.scenarios[1].scenario_id]
    assert handoff_draft.current_handoff.automation_scenario_ids == [analysis.scenarios[1].scenario_id]
    assert [item.scenario_id for item in pack.scenarios] == [analysis.scenarios[1].scenario_id]
    assert (
        f"纳入自动化 1 个，仅做回归 2 个，暂不处理 {len(analysis.scenarios) - 3} 个"
        in pack.context_summary
    )


def test_automation_plan_requires_automation_status_when_handoff_exists(controller):
    requirement = controller.create_requirement_input(
        title="库存冻结",
        markdown_content="# 库存冻结\n## 冻结库存\n## 解冻库存",
        image_paths=[],
        source="prd",
        notes="",
    )
    draft = controller.start_requirement_analysis(requirement)
    analysis = draft.latest_analysis
    assert analysis is not None

    scenario_statuses = {
        item.scenario_id: ScenarioHandoffStatus.REGRESSION_ONLY.value
        for item in analysis.scenarios
    }
    scenario_statuses[analysis.scenarios[1].scenario_id] = ScenarioHandoffStatus.DEFERRED.value
    controller.save_requirement_draft_handoff(scenario_statuses=scenario_statuses)
    controller.confirm_requirement_draft()

    with pytest.raises(ValueError, match="没有标记为“纳入自动化”的测试场景"):
        controller.plan_automation(
            requirement_title="库存冻结",
            page_summary="冻结后页面提示状态变化。",
            openapi_path="",
            target_type=ScenarioType.MIXED.value,
        )


def test_requirement_draft_handoff_requires_status_for_every_scenario(controller):
    requirement = controller.create_requirement_input(
        title="发票开具",
        markdown_content="# 发票开具\n## 新增发票\n## 红冲发票",
        image_paths=[],
        source="prd",
        notes="",
    )
    draft = controller.start_requirement_analysis(requirement)
    analysis = draft.latest_analysis
    assert analysis is not None

    with pytest.raises(ValueError, match="请为每个测试场景设置去向状态"):
        controller.save_requirement_draft_handoff(
            scenario_statuses={
                analysis.scenarios[0].scenario_id: ScenarioHandoffStatus.AUTOMATION.value,
            },
        )


def test_automation_plan_uses_openapi_summary(controller, tmp_path):
    requirement = controller.create_requirement_input(
        title="用户新增",
        markdown_content="# 用户新增\n- 新增表单提交后提示成功",
        image_paths=[],
        source="prd",
        notes="",
    )
    _confirm_requirement_record(controller, requirement)

    openapi_file = tmp_path / "openapi.json"
    openapi_file.write_text(
        """
        {
          "openapi": "3.0.0",
          "info": {"title": "User API", "version": "1.0.0"},
          "paths": {
            "/users": {
              "post": {
                "operationId": "createUser",
                "summary": "新增用户",
                "tags": ["user"],
                "responses": {"200": {"description": "ok"}}
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )

    pack = controller.plan_automation(
        requirement_title="用户新增",
        page_summary="用户新增页面包含姓名、手机号和角色字段。",
        openapi_path=str(openapi_file),
        target_type=ScenarioType.API.value,
    )

    assert pack.target_type == ScenarioType.API
    assert "createUser" in pack.coding_prompt
    assert pack.acceptance_checks
    assert "已读取测试场景处理方式" in pack.context_summary


def test_automation_plan_marks_missing_openapi_as_prerequisite(controller):
    requirement = controller.create_requirement_input(
        title="登录 API 自动化",
        markdown_content="# 登录\n## 登录成功\n## 登录失败",
        image_paths=[],
        source="prd",
        notes="",
    )
    _confirm_requirement_record(controller, requirement)

    pack = controller.plan_automation(
        requirement_title="登录 API 自动化",
        page_summary="登录页包含账号、密码输入框和错误提示区域。",
        openapi_path="",
        target_type=ScenarioType.API.value,
    )

    assert "自动化前置资料缺失" in pack.context_summary
    assert "未提供 OpenAPI/接口摘要" in pack.context_summary
    assert "自动化前置资料" in pack.coding_prompt


def test_automation_plan_sorts_scenarios_by_priority(controller):
    requirement = controller.create_requirement_input(
        title="优先级排序",
        markdown_content="# 登录\n## 登录成功\n## 登录失败\n## 账号锁定",
        image_paths=[],
        source="prd",
        notes="",
        scenario_detail_level=ScenarioDetailLevel.DETAILED.value,
    )
    _confirm_requirement_record(controller, requirement)

    pack = controller.plan_automation(
        requirement_title="优先级排序",
        page_summary="登录页包含账号、密码和错误提示。",
        openapi_path="",
        target_type=ScenarioType.MIXED.value,
    )

    priorities = [item.priority for item in pack.scenarios]
    assert priorities == sorted(priorities, key=lambda item: [ScenarioPriority.P0, ScenarioPriority.P1, ScenarioPriority.P2, ScenarioPriority.P3].index(item))
    assert "最高优先级" in pack.context_summary
    assert any(item.priority.value in pack.coding_prompt for item in pack.scenarios)


def test_formal_record_not_visible_before_confirm(controller):
    requirement = controller.create_requirement_input(
        title="正式记录前不可见",
        markdown_content="# 正式记录前不可见\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )
    controller.start_requirement_analysis(requirement)

    with pytest.raises(ValueError, match="未找到需求标题为“正式记录前不可见”的分析记录"):
        controller.plan_automation(
            requirement_title="正式记录前不可见",
            page_summary="页面描述",
            openapi_path="",
            target_type=ScenarioType.MIXED.value,
        )


def test_requirement_record_management_lists_and_counts_handoffs(controller):
    requirement = controller.create_requirement_input(
        title="采购审批",
        markdown_content="# 采购审批\n## 新建申请\n## 审批驳回",
        image_paths=[],
        source="prd",
        notes="需要区分审批角色",
    )
    draft = controller.start_requirement_analysis(requirement)
    analysis = draft.latest_analysis
    assert analysis is not None
    scenario_statuses = {
        item.scenario_id: ScenarioHandoffStatus.DEFERRED.value
        for item in analysis.scenarios
    }
    scenario_statuses[analysis.scenarios[0].scenario_id] = ScenarioHandoffStatus.AUTOMATION.value
    scenario_statuses[analysis.scenarios[1].scenario_id] = ScenarioHandoffStatus.REGRESSION_ONLY.value
    scenario_statuses[analysis.scenarios[2].scenario_id] = ScenarioHandoffStatus.DEFERRED.value
    controller.save_requirement_draft_handoff(scenario_statuses=scenario_statuses)
    controller.confirm_requirement_draft()

    records = controller.list_requirement_records()

    assert records
    assert records[0].requirement_id == requirement.id
    assert records[0].handoff_saved is True
    assert records[0].automation_count == 1
    assert records[0].regression_count == 1
    assert records[0].deferred_count == len(analysis.scenarios) - 2

    detail = controller.get_requirement_record(requirement.id)

    assert detail.requirement.title == "采购审批"
    assert detail.analysis.requirement_id == requirement.id
    assert detail.handoff is not None
    assert detail.refinement_history


def test_requirement_record_management_can_delete_saved_analysis(controller):
    requirement = controller.create_requirement_input(
        title="会员等级",
        markdown_content="# 会员等级\n## 升级规则\n## 降级规则",
        image_paths=[],
        source="prd",
        notes="",
    )
    analysis, _record = _confirm_requirement_record(controller, requirement)

    controller.delete_requirement_record(requirement.id)

    assert controller.list_requirement_records() == []
    with pytest.raises(ValueError, match="未找到对应的需求分析记录"):
        controller.get_requirement_record(requirement.id)
    assert controller.database.get_analysis(requirement.id) is None
    assert controller.database.list_scenarios([item.scenario_id for item in analysis.scenarios]) == []


def test_requirement_record_persists_business_categories(controller):
    controller.save_business_categories(
        [
            BusinessCategory(
                code="trade",
                name="交易中心",
                children=[BusinessSubcategory(code="refund", name="退款")],
            )
        ]
    )
    requirement = controller.create_requirement_input(
        title="退款审批",
        markdown_content="# 退款审批\n## 主流程",
        image_paths=[],
        source="prd",
        notes="需要补齐退款原因校验",
        business_level1_code="trade",
        business_level1_name="交易中心",
        business_level2_code="refund",
        business_level2_name="退款",
    )

    _confirm_requirement_record(controller, requirement)
    records = controller.list_requirement_records()
    detail = controller.get_requirement_record(requirement.id)

    assert records[0].business_path == "交易中心 / 退款"
    assert detail.requirement.business_level1_code == "trade"
    assert detail.requirement.business_level1_name == "交易中心"
    assert detail.requirement.business_level2_code == "refund"
    assert detail.requirement.business_level2_name == "退款"


def test_confirm_requirement_draft_replaces_stale_scenarios(controller):
    requirement = controller.create_requirement_input(
        title="审批范围收缩",
        markdown_content="# 审批范围收缩\n## 新建申请\n## 审批通过\n## 审批驳回",
        image_paths=[],
        source="prd",
        notes="",
    )
    initial_analysis, _record = _confirm_requirement_record(controller, requirement)

    draft = controller.create_requirement_draft_from_record(requirement.id)
    assert draft.latest_analysis is not None
    refined_requirement = controller.create_requirement_input(
        title="审批范围收缩",
        markdown_content="# 审批范围收缩\n## 新建申请",
        image_paths=[],
        source="prd",
        notes="只保留核心主流程",
        requirement_id=draft.requirement.id,
        created_at=draft.requirement.created_at,
    )
    refined_draft = controller.refine_requirement_analysis(
        requirement=refined_requirement,
        user_input="本次只保留主流程测试",
    )

    assert refined_draft.latest_analysis is not None
    controller.save_requirement_draft_handoff(
        scenario_statuses=_default_statuses(refined_draft.latest_analysis)
    )
    controller.confirm_requirement_draft()

    saved_scenarios = controller.database.list_scenarios()
    saved_ids = {item.scenario_id for item in saved_scenarios}

    assert len(saved_scenarios) == len(refined_draft.latest_analysis.scenarios)
    assert all(item.scenario_id in saved_ids for item in refined_draft.latest_analysis.scenarios)
    assert any(item.scenario_id not in saved_ids for item in initial_analysis.scenarios[1:])


def test_database_repairs_legacy_requirement_links(tmp_path):
    controller = build_controller(tmp_path)
    requirement = controller.create_requirement_input(
        title="历史数据修复",
        markdown_content="# 历史数据修复\n## 主流程",
        image_paths=[],
        source="prd",
        notes="",
    )
    analysis, _record = _confirm_requirement_record(controller, requirement)

    broken_analysis = analysis.model_copy(update={"requirement_id": requirement.title})
    with sqlite3.connect(controller.database.database_path) as connection:
        connection.execute(
            """
            UPDATE analyses
            SET requirement_id = ?, payload = ?
            WHERE requirement_id = ?
            """,
            (
                requirement.title,
                broken_analysis.model_dump_json(),
                requirement.id,
            ),
        )
        connection.execute(
            """
            UPDATE scenarios
            SET requirement_id = ?
            WHERE requirement_id = ?
            """,
            (
                requirement.title,
                requirement.id,
            ),
        )

    repaired_controller = build_controller(tmp_path)

    records = repaired_controller.list_requirement_records()
    detail = repaired_controller.get_requirement_record(requirement.id)

    assert records
    assert records[0].requirement_id == requirement.id
    assert detail.analysis.requirement_id == requirement.id
