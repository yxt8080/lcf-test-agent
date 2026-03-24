from __future__ import annotations

from datetime import datetime
import uuid

from local_test_agent.agents import (
    AutomationPlanningAgent,
    DefectDraftAgent,
    RegressionRoutingAgent,
    RequirementAnalysisAgent,
)
from local_test_agent.config import AppSettings
from local_test_agent.models import (
    BusinessCategory,
    BusinessCategoryOption,
    BusinessSubcategory,
    CodegenTaskPack,
    DefectDraft,
    ExecutionRequest,
    ExecutionResult,
    LLMCallLogEntry,
    RegressionSuggestion,
    LLMConnectionTestResult,
    RequirementAnalysisDraft,
    RequirementDraftSource,
    RequirementHandoff,
    RequirementHandoffDecision,
    RequirementInput,
    RequirementRefinementRound,
    RequirementRecordDetail,
    RequirementRecordSummary,
    RuntimeLogEntry,
    ScenarioDescriptor,
    ScenarioDetailLevel,
    ScenarioHandoffStatus,
    ScenarioPriority,
    ScenarioType,
    TestAnalysisResult,
)
from local_test_agent.adapters.llm import LLMAdapter
from local_test_agent.services.artifact_collector import ArtifactCollector
from local_test_agent.services.openapi_parser import OpenAPIParser
from local_test_agent.services.report_builder import ReportBuilder
from local_test_agent.services.runtime_logger import RuntimeLogger
from local_test_agent.services.scenario_index import ScenarioIndexService
from local_test_agent.services.test_executor import TestExecutor
from local_test_agent.store.config_store import ConfigStore
from local_test_agent.store.database import LocalDatabase
from local_test_agent.store.llm_log_store import LLMLogStore
from local_test_agent.store.runtime_log_store import RuntimeLogStore
from local_test_agent.adapters.yunxiao import YunxiaoAdapter
from local_test_agent.models.schemas import now_utc


class WorkbenchController:
    """统一暴露桌面端调用接口，避免页面层直接操作底层服务。"""

    def __init__(
        self,
        *,
        settings: AppSettings,
        config_store: ConfigStore,
        database: LocalDatabase,
        llm_log_store: LLMLogStore,
        runtime_log_store: RuntimeLogStore,
        runtime_logger: RuntimeLogger,
        requirement_agent: RequirementAnalysisAgent,
        automation_agent: AutomationPlanningAgent,
        regression_agent: RegressionRoutingAgent,
        defect_agent: DefectDraftAgent,
        openapi_parser: OpenAPIParser,
        scenario_index: ScenarioIndexService,
        artifact_collector: ArtifactCollector,
        report_builder: ReportBuilder,
        test_executor: TestExecutor,
        yunxiao_adapter: YunxiaoAdapter,
    ) -> None:
        self.settings = settings
        self.config_store = config_store
        self.database = database
        self.llm_log_store = llm_log_store
        self.runtime_log_store = runtime_log_store
        self.runtime_logger = runtime_logger
        self.requirement_agent = requirement_agent
        self.automation_agent = automation_agent
        self.regression_agent = regression_agent
        self.defect_agent = defect_agent
        self.openapi_parser = openapi_parser
        self.scenario_index = scenario_index
        self.artifact_collector = artifact_collector
        self.report_builder = report_builder
        self.test_executor = test_executor
        self.yunxiao_adapter = yunxiao_adapter

    def analyze_requirement(self, requirement: RequirementInput) -> TestAnalysisResult:
        draft = self.start_requirement_analysis(requirement)
        if draft.latest_analysis is None:
            raise ValueError("需求分析未产出可用结果。")
        return draft.latest_analysis

    def get_active_requirement_draft(self) -> RequirementAnalysisDraft | None:
        return self.database.get_active_requirement_draft()

    def start_requirement_analysis(self, requirement: RequirementInput) -> RequirementAnalysisDraft:
        self.runtime_logger.info(
            "requirement.analysis.start",
            "开始生成需求分析草稿。",
            requirement_id=requirement.id,
            title=requirement.title,
            scenario_detail_level=requirement.scenario_detail_level.value,
        )
        try:
            result = self._normalize_analysis_requirement_id(
                self.requirement_agent.analyze(requirement),
                requirement_id=requirement.id,
            )
            refinement_history = [
                RequirementRefinementRound(
                    round_index=1,
                    user_input="初次分析",
                    analysis_summary=result.summary,
                    change_summary=self._build_analysis_change_summary(None, result),
                )
            ]
            draft = RequirementAnalysisDraft(
                requirement=requirement,
                latest_analysis=result,
                current_handoff=self._build_default_handoff(requirement.id, result.scenarios),
                refinement_history=refinement_history,
                source=RequirementDraftSource.NEW,
                handoff_confirmed=False,
            )
            self.database.save_active_requirement_draft(draft)
            self.runtime_logger.info(
                "requirement.analysis.success",
                "需求分析草稿已保存。",
                requirement_id=requirement.id,
                feature_count=len(result.features),
                scenario_count=len(result.scenarios),
                risk_count=len(result.risks),
                open_question_count=len(result.open_questions),
            )
            return draft
        except Exception:
            self.runtime_logger.exception(
                "requirement.analysis.failed",
                "需求分析草稿生成失败。",
                requirement_id=requirement.id,
                title=requirement.title,
            )
            raise

    def refine_requirement_analysis(
        self,
        *,
        requirement: RequirementInput,
        user_input: str,
    ) -> RequirementAnalysisDraft:
        draft = self.database.get_active_requirement_draft()
        if draft is None or draft.latest_analysis is None:
            raise ValueError("当前没有可继续完善的需求分析草稿。")

        normalized_user_input = user_input.strip()
        if not normalized_user_input:
            raise ValueError("请先输入本轮补充说明，再继续完善。")

        # 草稿完善阶段始终沿用同一个 requirement_id，避免最终确认保存时丢失对正式记录的覆盖关系。
        normalized_requirement = requirement.model_copy(
            update={
                "id": draft.requirement.id,
                "created_at": draft.requirement.created_at,
            }
        )
        self.runtime_logger.info(
            "requirement.refine.start",
            "开始基于补充说明完善需求分析。",
            requirement_id=normalized_requirement.id,
            refinement_round=len(draft.refinement_history) + 1,
        )
        try:
            result = self._normalize_analysis_requirement_id(
                self.requirement_agent.analyze(
                    normalized_requirement,
                    refinement_history=draft.refinement_history,
                    latest_user_input=normalized_user_input,
                ),
                requirement_id=normalized_requirement.id,
            )
            updated_history = [
                *draft.refinement_history,
                RequirementRefinementRound(
                    round_index=len(draft.refinement_history) + 1,
                    user_input=normalized_user_input,
                    analysis_summary=result.summary,
                    change_summary=self._build_analysis_change_summary(draft.latest_analysis, result),
                ),
            ]
            updated_draft = RequirementAnalysisDraft(
                requirement=normalized_requirement,
                latest_analysis=result,
                current_handoff=self._build_default_handoff(normalized_requirement.id, result.scenarios),
                refinement_history=updated_history,
                source=draft.source,
                handoff_confirmed=False,
            )
            self.database.save_active_requirement_draft(updated_draft)
            self.runtime_logger.info(
                "requirement.refine.success",
                "需求分析完善结果已保存。",
                requirement_id=normalized_requirement.id,
                refinement_round=len(updated_history),
                scenario_count=len(result.scenarios),
            )
            return updated_draft
        except Exception:
            self.runtime_logger.exception(
                "requirement.refine.failed",
                "需求分析完善失败。",
                requirement_id=normalized_requirement.id,
            )
            raise

    def save_requirement_draft_handoff(
        self,
        *,
        scenario_statuses: dict[str, str],
    ) -> RequirementAnalysisDraft:
        draft = self.database.get_active_requirement_draft()
        if draft is None or draft.latest_analysis is None:
            raise ValueError("当前没有可确认场景处理方式的需求分析草稿。")

        try:
            handoff = self._build_requirement_handoff(
                requirement_id=draft.requirement.id,
                analysis=draft.latest_analysis,
                scenario_statuses=scenario_statuses,
            )
            updated_draft = draft.model_copy(
                update={
                    "current_handoff": handoff,
                    "handoff_confirmed": True,
                    "last_updated_at": now_utc(),
                }
            )
            self.database.save_active_requirement_draft(updated_draft)
            self.runtime_logger.info(
                "requirement.handoff.save",
                "需求草稿的场景去向已确认。",
                requirement_id=draft.requirement.id,
                automation_count=len(handoff.automation_scenario_ids),
                selected_count=len(handoff.selected_scenario_ids),
            )
            return updated_draft
        except Exception:
            self.runtime_logger.exception(
                "requirement.handoff.failed",
                "保存需求草稿场景去向失败。",
                requirement_id=draft.requirement.id,
            )
            raise

    def confirm_requirement_draft(self) -> RequirementRecordDetail:
        draft = self.database.get_active_requirement_draft()
        if draft is None or draft.latest_analysis is None:
            raise ValueError("当前没有可保存的需求分析草稿。")
        if draft.current_handoff is None or not draft.handoff_confirmed:
            raise ValueError("请先确认场景处理方式，再保存正式记录。")

        try:
            normalized_analysis = self._normalize_analysis_requirement_id(
                draft.latest_analysis,
                requirement_id=draft.requirement.id,
            )
            self.database.save_requirement_record(
                requirement=draft.requirement,
                analysis=normalized_analysis,
                handoff=draft.current_handoff,
                refinement_history=draft.refinement_history,
            )
            self.database.delete_active_requirement_draft()
            self.runtime_logger.info(
                "requirement.confirm.success",
                "需求分析正式记录已保存。",
                requirement_id=draft.requirement.id,
                scenario_count=len(normalized_analysis.scenarios),
                refinement_round=len(draft.refinement_history),
            )
            return self.get_requirement_record(draft.requirement.id)
        except Exception:
            self.runtime_logger.exception(
                "requirement.confirm.failed",
                "保存需求正式记录失败。",
                requirement_id=draft.requirement.id,
            )
            raise

    def discard_requirement_draft(self) -> None:
        self.database.delete_active_requirement_draft()

    def create_requirement_draft_from_record(self, requirement_id: str) -> RequirementAnalysisDraft:
        record = self.get_requirement_record(requirement_id)
        draft = RequirementAnalysisDraft(
            requirement=record.requirement,
            latest_analysis=record.analysis,
            current_handoff=record.handoff
            or self._build_default_handoff(record.requirement.id, record.analysis.scenarios),
            refinement_history=record.refinement_history,
            source=RequirementDraftSource.RECORD_EDIT,
            handoff_confirmed=record.handoff is not None,
        )
        self.database.save_active_requirement_draft(draft)
        return draft

    def list_requirement_records(self) -> list[RequirementRecordSummary]:
        return self.database.list_requirement_records()

    def get_requirement_record(self, requirement_id: str) -> RequirementRecordDetail:
        record = self.database.get_requirement_record(requirement_id)
        if record is None:
            raise ValueError("未找到对应的需求分析记录。")
        return record

    def delete_requirement_record(self, requirement_id: str) -> None:
        deleted = self.database.delete_requirement_record(requirement_id)
        if not deleted:
            raise ValueError("未找到可删除的需求分析记录。")

    def save_requirement_handoff(
        self,
        *,
        requirement_id: str,
        scenario_statuses: dict[str, str],
    ) -> RequirementHandoff:
        analysis = self.database.get_analysis(requirement_id)
        if analysis is None:
            raise ValueError("该需求尚未生成测试分析结果，无法保存交接场景。")
        handoff = self._build_requirement_handoff(
            requirement_id=requirement_id,
            analysis=analysis,
            scenario_statuses=scenario_statuses,
        )
        self.database.save_requirement_handoff(handoff)
        return handoff

    def create_requirement_input(
        self,
        *,
        title: str,
        markdown_content: str,
        image_paths: list[str],
        source: str,
        notes: str = "",
        business_level1_code: str = "",
        business_level1_name: str = "",
        business_level2_code: str = "",
        business_level2_name: str = "",
        scenario_detail_level: str = ScenarioDetailLevel.STANDARD.value,
        requirement_id: str | None = None,
        created_at: datetime | None = None,
    ) -> RequirementInput:
        return RequirementInput(
            id=requirement_id or str(uuid.uuid4()),
            title=title.strip() or "未命名需求",
            markdown_content=markdown_content,
            scenario_detail_level=ScenarioDetailLevel(scenario_detail_level),
            image_paths=image_paths,
            source=source.strip() or "manual",
            notes=notes,
            # 需求录入阶段直接挂接统一业务字典，后续自动化、回归和缺陷模块都可复用这组归属信息。
            business_level1_code=business_level1_code.strip(),
            business_level1_name=business_level1_name.strip(),
            business_level2_code=business_level2_code.strip(),
            business_level2_name=business_level2_name.strip(),
            created_at=created_at or now_utc(),
        )

    def plan_automation(
        self,
        *,
        requirement_title: str,
        page_summary: str,
        openapi_path: str,
        target_type: str,
    ) -> CodegenTaskPack:
        self.runtime_logger.info(
            "automation.plan.start",
            "开始生成自动化任务包。",
            requirement_title=requirement_title,
            target_type=target_type,
            has_openapi=bool(openapi_path.strip()),
        )
        try:
            requirement = self.database.find_requirement_by_title(requirement_title)
            if requirement is None:
                raise ValueError(f"未找到需求标题为“{requirement_title}”的分析记录。")
            analysis = self.database.get_analysis(requirement.id)
            if analysis is None:
                raise ValueError("该需求尚未生成测试分析结果。")
            scoped_analysis, selection_summary = self._build_handoff_analysis(analysis)
            openapi_summary = (
                self.openapi_parser.parse(openapi_path)
                if openapi_path.strip()
                else {"title": "", "version": "", "operation_count": 0, "operations": []}
            )
            pack = self.automation_agent.plan(
                self._sort_scenarios_by_priority(scoped_analysis),
                page_summary=page_summary,
                openapi_summary=openapi_summary,
                target_type=ScenarioType(target_type),
            )
            pack.context_summary = f"{selection_summary} {pack.context_summary}".strip()
            self.runtime_logger.info(
                "automation.plan.success",
                "自动化任务包生成完成。",
                requirement_id=requirement.id,
                scenario_count=len(pack.scenarios),
                target_type=pack.target_type.value,
            )
            return pack
        except Exception:
            self.runtime_logger.exception(
                "automation.plan.failed",
                "自动化任务包生成失败。",
                requirement_title=requirement_title,
                target_type=target_type,
            )
            raise

    def recommend_regression(self, bug_description: str) -> list[RegressionSuggestion]:
        self.runtime_logger.info(
            "regression.recommend.start",
            "开始生成回归推荐。",
            bug_description_length=len(bug_description.strip()),
        )
        try:
            candidates = self.scenario_index.search(bug_description)
            used_full_scan = False
            if not candidates:
                candidates = self.database.list_scenarios()
                used_full_scan = True
            suggestions = self.regression_agent.recommend(bug_description, candidates)
            self.runtime_logger.info(
                "regression.recommend.success",
                "回归推荐已生成。",
                candidate_count=len(candidates),
                suggestion_count=len(suggestions),
                used_full_scan=used_full_scan,
            )
            return suggestions
        except Exception:
            self.runtime_logger.exception(
                "regression.recommend.failed",
                "回归推荐生成失败。",
                bug_description_length=len(bug_description.strip()),
            )
            raise

    def create_execution_request(
        self,
        *,
        scenario_ids: list[str],
        env_name: str,
        trigger_reason: str,
        target_type: str,
        pytest_args: list[str] | None = None,
        dry_run: bool = False,
    ) -> ExecutionRequest:
        return ExecutionRequest(
            request_id=str(uuid.uuid4()),
            scenario_ids=[item.strip() for item in scenario_ids if item.strip()],
            env_name=env_name.strip() or "test",
            trigger_reason=trigger_reason.strip() or "manual",
            target_type=ScenarioType(target_type),
            pytest_args=pytest_args or [],
            dry_run=dry_run,
        )

    def run_tests(self, request: ExecutionRequest) -> ExecutionResult:
        self.runtime_logger.info(
            "execution.run.start",
            "开始执行测试请求。",
            request_id=request.request_id,
            scenario_count=len(request.scenario_ids),
            target_type=request.target_type.value,
            dry_run=request.dry_run,
        )
        try:
            result = self.test_executor.run_tests(request)
            artifacts = self.artifact_collector.collect(request, result)
            result.artifacts.extend(artifacts)
            self.database.save_execution_result(result)
            self.runtime_logger.info(
                "execution.run.success",
                "测试执行结果已落库。",
                request_id=request.request_id,
                status=result.status.value,
                failed=result.failed,
                artifact_count=len(result.artifacts),
            )
            return result
        except Exception:
            self.runtime_logger.exception(
                "execution.run.failed",
                "测试执行链路失败。",
                request_id=request.request_id,
            )
            raise

    def generate_execution_report(self, request_id: str | None = None) -> dict[str, str]:
        try:
            result = (
                self.database.get_execution_result(request_id)
                if request_id
                else self.database.get_latest_execution_result()
            )
            if result is None:
                raise ValueError("未找到可生成报告的执行记录。")
            markdown_path, html_path = self.report_builder.build_execution_report(result)
            self.runtime_logger.info(
                "report.execution.success",
                "执行报告已生成。",
                request_id=result.request_id,
                markdown_path=str(markdown_path),
                html_path=str(html_path),
            )
            return {"markdown": str(markdown_path), "html": str(html_path)}
        except Exception:
            self.runtime_logger.exception(
                "report.execution.failed",
                "生成执行报告失败。",
                request_id=request_id or "",
            )
            raise

    def build_defect_draft(
        self,
        request_id: str | None = None,
        *,
        requirement_id: str | None = None,
        environment: str = "test",
    ) -> DefectDraft:
        try:
            result = (
                self.database.get_execution_result(request_id)
                if request_id
                else self.database.get_latest_execution_result()
            )
            if result is None:
                raise ValueError("未找到执行结果，无法生成缺陷草稿。")
            draft = self.defect_agent.build_draft(
                result,
                requirement_id=requirement_id,
                environment=environment,
            )
            preview_path = self.report_builder.build_defect_preview(draft)
            draft.attachments.append(str(preview_path))
            self.database.save_defect_draft(draft)
            self.runtime_logger.info(
                "defect.draft.success",
                "缺陷草稿已生成并保存。",
                request_id=result.request_id,
                requirement_id=requirement_id or "",
                attachment_count=len(draft.attachments),
            )
            return draft
        except Exception:
            self.runtime_logger.exception(
                "defect.draft.failed",
                "生成缺陷草稿失败。",
                request_id=request_id or "",
                requirement_id=requirement_id or "",
            )
            raise

    def submit_defect(self, draft: DefectDraft) -> str:
        self.runtime_logger.info(
            "defect.submit.start",
            "开始提交缺陷草稿。",
            request_id=draft.execution_request_id,
            requirement_id=draft.requirement_id or "",
        )
        try:
            defect_id = self.yunxiao_adapter.submit_defect(draft)
            self.runtime_logger.info(
                "defect.submit.success",
                "缺陷草稿提交完成。",
                request_id=draft.execution_request_id,
                defect_id=defect_id,
            )
            return defect_id
        except Exception:
            self.runtime_logger.exception(
                "defect.submit.failed",
                "提交缺陷草稿失败。",
                request_id=draft.execution_request_id,
            )
            raise

    def save_settings(self, payload: dict[str, str]) -> None:
        self._apply_llm_settings_payload(self.settings, payload)
        self._apply_yunxiao_settings_payload(self.settings, payload)
        self.config_store.save(self.settings)

    def save_llm_settings(self, payload: dict[str, str]) -> None:
        self._apply_llm_settings_payload(self.settings, payload)
        self.config_store.save(self.settings)
        self.runtime_logger.info(
            "settings.llm.save",
            "模型配置已保存。",
            provider_model=self.settings.llm.provider_model,
            live_mode_enabled=self.settings.llm.enable_live_llm,
        )

    def save_yunxiao_settings(self, payload: dict[str, str]) -> None:
        self._apply_yunxiao_settings_payload(self.settings, payload)
        self.config_store.save(self.settings)
        self.runtime_logger.info(
            "settings.yunxiao.save",
            "云效配置已保存。",
            api_base_url=self.settings.yunxiao.api_base_url,
            project_id=self.settings.yunxiao.project_id,
        )

    def test_llm_settings(self, payload: dict[str, str]) -> LLMConnectionTestResult:
        # 配置测试只读取页面当前草稿值，避免用户为了试连通性被迫先落盘正式配置。
        candidate_settings = self.settings.model_copy(deep=True)
        self._apply_llm_settings_payload(candidate_settings, payload)
        self.runtime_logger.info(
            "settings.llm.test.start",
            "开始测试模型配置。",
            provider_model=candidate_settings.llm.provider_model,
            live_mode_enabled=candidate_settings.llm.enable_live_llm,
        )
        try:
            result = LLMAdapter(candidate_settings.llm, log_store=self.llm_log_store).test_connection()
            self.runtime_logger.info(
                "settings.llm.test.success",
                "模型配置测试完成。",
                provider_model=result.provider_model,
                success=result.success,
                basic_connectivity_ok=result.basic_connectivity_ok,
                structured_output_ok=result.structured_output_ok,
            )
            return result
        except Exception:
            self.runtime_logger.exception(
                "settings.llm.test.failed",
                "模型配置测试失败。",
                provider_model=candidate_settings.llm.provider_model,
            )
            raise

    def load_settings(self) -> dict[str, str]:
        return self.config_store.export_flat_payload(self.settings)

    def list_recent_llm_logs(self, limit: int = 100) -> list[LLMCallLogEntry]:
        return self.llm_log_store.read_recent(limit=limit)

    def clear_llm_logs(self) -> None:
        self.llm_log_store.clear()
        self.runtime_logger.info("logs.llm.clear", "模型调用日志已清空。")

    def list_recent_runtime_logs(self, limit: int = 100) -> list[RuntimeLogEntry]:
        return self.runtime_log_store.read_recent(limit=limit)

    def clear_runtime_logs(self) -> None:
        self.runtime_log_store.clear()

    def list_business_categories(self) -> list[BusinessCategory]:
        return [item.model_copy(deep=True) for item in self.settings.business.categories]

    def list_business_category_options(self) -> list[BusinessCategoryOption]:
        options: list[BusinessCategoryOption] = []
        for category in self.settings.business.categories:
            if not category.children:
                options.append(
                    BusinessCategoryOption(
                        value=category.code,
                        label=category.name,
                        level1_code=category.code,
                        level1_name=category.name,
                    )
                )
                continue

            # 下游模块通常要选择叶子归属，这里统一展平成“一级 / 二级”选项，避免每页重复拼装。
            for child in category.children:
                options.append(
                    BusinessCategoryOption(
                        value=f"{category.code}/{child.code}",
                        label=f"{category.name} / {child.name}",
                        level1_code=category.code,
                        level1_name=category.name,
                        level2_code=child.code,
                        level2_name=child.name,
                    )
                )
        return options

    def save_business_categories(self, categories: list[BusinessCategory]) -> list[BusinessCategory]:
        normalized_categories = self._normalize_business_categories(categories)
        self.settings.business.categories = normalized_categories
        self.config_store.save(self.settings)
        return self.list_business_categories()

    def export_runtime_state(self) -> dict[str, object]:
        return {
            "settings": self.load_settings(),
            "database": self.database.export_state(),
            "business_categories": [item.model_dump(mode="json") for item in self.settings.business.categories],
        }

    def _apply_llm_settings_payload(self, settings: AppSettings, payload: dict[str, str]) -> None:
        settings.llm.provider_model = payload.get("llm_provider_model", settings.llm.provider_model)
        settings.llm.base_url = payload.get("llm_base_url", settings.llm.base_url)
        settings.llm.enable_live_llm = payload.get("llm_enable_live", "false").lower() == "true"
        settings.llm.api_key = payload.get("llm_api_key", settings.llm.api_key)

    def _apply_yunxiao_settings_payload(self, settings: AppSettings, payload: dict[str, str]) -> None:
        settings.yunxiao.api_base_url = payload.get("yunxiao_api_base_url", settings.yunxiao.api_base_url)
        settings.yunxiao.organization_id = payload.get(
            "yunxiao_organization_id",
            settings.yunxiao.organization_id,
        )
        settings.yunxiao.project_id = payload.get("yunxiao_project_id", settings.yunxiao.project_id)
        settings.yunxiao.create_defect_path = payload.get(
            "yunxiao_create_defect_path",
            settings.yunxiao.create_defect_path,
        )
        settings.yunxiao.access_token = payload.get(
            "yunxiao_access_token",
            settings.yunxiao.access_token,
        )

    def _build_handoff_analysis(
        self,
        analysis: TestAnalysisResult,
    ) -> tuple[TestAnalysisResult, str]:
        handoff = self.database.get_requirement_handoff(analysis.requirement_id)
        if handoff is None:
            return (
                analysis,
                f"未找到已确认的测试场景处理方式，当前回退使用需求分析中的 {len(analysis.scenarios)} 个测试场景。",
            )

        selected_scenarios = self._resolve_selected_scenarios(analysis, handoff.automation_scenario_ids)
        if not selected_scenarios:
            raise ValueError("该需求当前没有标记为“纳入自动化”的测试场景，请先在需求分析页确认场景处理方式。")

        # 自动化设计只消费已明确纳入自动化的测试场景，避免把仅做回归或暂不处理项继续传下游。
        scoped_analysis = analysis.model_copy(update={"scenarios": selected_scenarios})
        counts = self._count_handoff_statuses(handoff)
        return (
            scoped_analysis,
            "已读取测试场景处理方式："
            f"纳入自动化 {counts[ScenarioHandoffStatus.AUTOMATION]} 个，"
            f"仅做回归 {counts[ScenarioHandoffStatus.REGRESSION_ONLY]} 个，"
            f"暂不处理 {counts[ScenarioHandoffStatus.DEFERRED]} 个。",
        )

    def _resolve_selected_scenarios(
        self,
        analysis: TestAnalysisResult,
        scenario_ids: list[str],
    ) -> list[ScenarioDescriptor]:
        scenario_map = {item.scenario_id: item for item in analysis.scenarios}
        return [
            scenario_map[item]
            for item in scenario_ids
            if item in scenario_map
        ]

    def _count_handoff_statuses(
        self,
        handoff: RequirementHandoff,
    ) -> dict[ScenarioHandoffStatus, int]:
        counts = {status: 0 for status in ScenarioHandoffStatus}
        if handoff.scenario_decisions:
            for item in handoff.scenario_decisions:
                counts[item.status] += 1
            return counts
        counts[ScenarioHandoffStatus.AUTOMATION] = len(handoff.selected_scenario_ids)
        return counts

    @staticmethod
    def _sort_scenarios_by_priority(analysis: TestAnalysisResult) -> TestAnalysisResult:
        priority_order = {
            ScenarioPriority.P0: 0,
            ScenarioPriority.P1: 1,
            ScenarioPriority.P2: 2,
            ScenarioPriority.P3: 3,
        }
        return analysis.model_copy(
            update={
                "scenarios": sorted(
                    analysis.scenarios,
                    key=lambda item: (priority_order.get(item.priority, 99), item.scenario_id),
                )
            }
        )

    def _build_requirement_handoff(
        self,
        *,
        requirement_id: str,
        analysis: TestAnalysisResult,
        scenario_statuses: dict[str, str],
    ) -> RequirementHandoff:
        valid_ids = {item.scenario_id for item in analysis.scenarios}
        normalized_statuses = {
            scenario_id.strip(): status.strip()
            for scenario_id, status in scenario_statuses.items()
            if scenario_id.strip()
        }
        if not normalized_statuses:
            raise ValueError("请先为至少一个测试场景设置去向状态。")

        invalid_ids = [item for item in normalized_statuses if item not in valid_ids]
        if invalid_ids:
            raise ValueError(f"存在无效场景编号，无法保存交接数据：{', '.join(invalid_ids)}")
        missing_ids = [item.scenario_id for item in analysis.scenarios if item.scenario_id not in normalized_statuses]
        if missing_ids:
            raise ValueError(f"请为每个测试场景设置去向状态，缺少：{', '.join(missing_ids)}")

        decisions: list[RequirementHandoffDecision] = []
        for scenario in analysis.scenarios:
            raw_status = normalized_statuses[scenario.scenario_id]
            try:
                status = ScenarioHandoffStatus(raw_status)
            except ValueError as exc:
                raise ValueError(f"场景 {scenario.scenario_id} 的去向状态不合法：{raw_status}") from exc
            decisions.append(
                RequirementHandoffDecision(
                    scenario_id=scenario.scenario_id,
                    status=status,
                )
            )

        automation_ids = [
            item.scenario_id for item in decisions if item.status is ScenarioHandoffStatus.AUTOMATION
        ]
        return RequirementHandoff(
            requirement_id=requirement_id,
            scenario_decisions=decisions,
            selected_scenario_ids=automation_ids,
        )

    def _build_default_handoff(
        self,
        requirement_id: str,
        scenarios: list[ScenarioDescriptor],
    ) -> RequirementHandoff:
        # 草稿每次重算后都回到“全部纳入自动化”的初始状态，避免旧选择误套到新场景集合上。
        return RequirementHandoff(
            requirement_id=requirement_id,
            scenario_decisions=[
                RequirementHandoffDecision(
                    scenario_id=item.scenario_id,
                    status=ScenarioHandoffStatus.AUTOMATION,
                )
                for item in scenarios
            ],
            selected_scenario_ids=[item.scenario_id for item in scenarios],
        )

    def _build_analysis_change_summary(
        self,
        previous: TestAnalysisResult | None,
        current: TestAnalysisResult,
    ) -> str:
        if previous is None:
            return (
                f"首次生成：功能点 {len(current.features)} 个，"
                f"场景 {len(current.scenarios)} 个，"
                f"风险 {len(current.risks)} 个，"
                f"待确认 {len(current.open_questions)} 个。"
            )

        def format_delta(current_count: int, previous_count: int) -> str:
            delta = current_count - previous_count
            if delta == 0:
                return f"{current_count}（无变化）"
            sign = "+" if delta > 0 else ""
            return f"{current_count}（{sign}{delta}）"

        return (
            "本轮变化："
            f"功能点 {format_delta(len(current.features), len(previous.features))}，"
            f"场景 {format_delta(len(current.scenarios), len(previous.scenarios))}，"
            f"风险 {format_delta(len(current.risks), len(previous.risks))}，"
            f"待确认 {format_delta(len(current.open_questions), len(previous.open_questions))}。"
        )

    @staticmethod
    def _normalize_analysis_requirement_id(
        analysis: TestAnalysisResult,
        *,
        requirement_id: str,
    ) -> TestAnalysisResult:
        if analysis.requirement_id == requirement_id:
            return analysis
        # 实时模型偶发会把 requirement_id 填成标题或自然语言描述，这里统一以输入 requirement.id 为准。
        return analysis.model_copy(update={"requirement_id": requirement_id})

    def _normalize_business_categories(
        self,
        categories: list[BusinessCategory],
    ) -> list[BusinessCategory]:
        normalized_categories: list[BusinessCategory] = []
        seen_level1_codes: set[str] = set()
        seen_level1_names: set[str] = set()

        for category in categories:
            category_code = category.code.strip()
            category_name = category.name.strip()
            if not category_code or not category_name:
                raise ValueError("一级业务分类的编码和名称都不能为空。")
            if category_code in seen_level1_codes:
                raise ValueError(f"一级业务分类编码重复：{category_code}")
            if category_name in seen_level1_names:
                raise ValueError(f"一级业务分类名称重复：{category_name}")
            seen_level1_codes.add(category_code)
            seen_level1_names.add(category_name)

            seen_level2_codes: set[str] = set()
            seen_level2_names: set[str] = set()
            normalized_children: list[BusinessSubcategory] = []
            for child in category.children:
                child_code = child.code.strip()
                child_name = child.name.strip()
                if not child_code or not child_name:
                    raise ValueError(f"一级业务“{category_name}”下存在空的二级分类编码或名称。")
                if child_code in seen_level2_codes:
                    raise ValueError(f"一级业务“{category_name}”下的二级分类编码重复：{child_code}")
                if child_name in seen_level2_names:
                    raise ValueError(f"一级业务“{category_name}”下的二级分类名称重复：{child_name}")
                seen_level2_codes.add(child_code)
                seen_level2_names.add(child_name)
                normalized_children.append(BusinessSubcategory(code=child_code, name=child_name))

            normalized_categories.append(
                BusinessCategory(
                    code=category_code,
                    name=category_name,
                    children=normalized_children,
                )
            )

        return normalized_categories
