from __future__ import annotations

from local_test_agent.models import DefectDraft, ExecutionStatus


def _prepare_requirement(controller):
    requirement = controller.create_requirement_input(
        title="审批配置",
        markdown_content="# 审批配置\n- 支持新增审批节点\n- 支持删除审批节点",
        image_paths=[],
        source="prd",
        notes="",
    )
    draft = controller.start_requirement_analysis(requirement)
    assert draft.latest_analysis is not None
    controller.save_requirement_draft_handoff(
        scenario_statuses={
            item.scenario_id: "automation"
            for item in draft.latest_analysis.scenarios
        }
    )
    controller.confirm_requirement_draft()
    return draft.latest_analysis


def test_regression_recommendation_returns_ranked_scenarios(controller):
    analysis = _prepare_requirement(controller)

    suggestions = controller.recommend_regression("审批节点删除后页面提示异常")

    assert suggestions
    assert suggestions[0].scenario_id in {item.scenario_id for item in analysis.scenarios}
    assert suggestions[0].score >= suggestions[-1].score


def test_run_tests_and_build_report(controller):
    analysis = _prepare_requirement(controller)
    request = controller.create_execution_request(
        scenario_ids=[analysis.scenarios[0].scenario_id],
        env_name="test",
        trigger_reason="bugfix",
        target_type="ui",
        dry_run=True,
    )

    result = controller.run_tests(request)
    report = controller.generate_execution_report(result.request_id)

    assert result.status == ExecutionStatus.SUCCESS
    assert report["markdown"].endswith(".md")
    assert report["html"].endswith(".html")


def test_build_defect_draft(controller):
    request = controller.create_execution_request(
        scenario_ids=[],
        env_name="test",
        trigger_reason="manual",
        target_type="mixed",
        dry_run=False,
        pytest_args=["tests/test_non_existing.py"],
    )

    result = controller.run_tests(request)
    draft = controller.build_defect_draft(result.request_id, requirement_id="REQ-DEMO")

    assert isinstance(draft, DefectDraft)
    assert draft.execution_request_id == result.request_id
    assert draft.attachments
