from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def now_utc() -> datetime:
    return datetime.now(UTC)


class ScenarioType(str, Enum):
    UI = "ui"
    API = "api"
    MIXED = "mixed"


class ScenarioDetailLevel(str, Enum):
    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"


class ScenarioPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ScenarioKind(str, Enum):
    MAIN_FLOW = "main_flow"
    KEY_EXCEPTION = "key_exception"
    BOUNDARY = "boundary"
    PERMISSION = "permission"
    STATE_TRANSITION = "state_transition"


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    RUNNING = "running"


class RuntimeLogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ScenarioHandoffStatus(str, Enum):
    AUTOMATION = "automation"
    REGRESSION_ONLY = "regression_only"
    DEFERRED = "deferred"


class RequirementDraftSource(str, Enum):
    NEW = "new"
    RECORD_EDIT = "record_edit"


class AnalysisFeature(BaseModel):
    name: str
    summary: str
    source_excerpt: str = ""


class TestPath(BaseModel):
    name: str
    objective: str
    scenario_ids: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    title: str
    level: str
    impact: str
    mitigation: str


class OpenQuestion(BaseModel):
    question: str
    reason: str


class CheckPoint(BaseModel):
    title: str
    detail: str


class BusinessSubcategory(BaseModel):
    code: str
    name: str


class BusinessCategory(BaseModel):
    code: str
    name: str
    children: list[BusinessSubcategory] = Field(default_factory=list)


class BusinessCategoryOption(BaseModel):
    value: str
    label: str
    level1_code: str
    level1_name: str
    level2_code: str | None = None
    level2_name: str | None = None


class ScenarioDescriptor(BaseModel):
    scenario_id: str
    title: str
    summary: str = ""
    priority: ScenarioPriority = ScenarioPriority.P2
    scenario_kind: ScenarioKind = ScenarioKind.MAIN_FLOW
    module: str
    automation_type: ScenarioType = ScenarioType.MIXED
    tags: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)
    related_api_ids: list[str] = Field(default_factory=list)
    related_pages: list[str] = Field(default_factory=list)
    checkpoints: list[CheckPoint] = Field(default_factory=list)
    test_selector: str | None = None

    @model_validator(mode="after")
    def ensure_readable_defaults(self) -> "ScenarioDescriptor":
        # 旧记录里可能没有 summary / priority 字段，这里统一补默认可读值，
        # 保证需求分析页、自动化任务包和回归推荐在加载历史数据时不会出现空白描述。
        if not self.summary.strip():
            step_text = self.steps[0] if self.steps else "执行核心测试步骤"
            assertion_text = self.assertions[0] if self.assertions else "检查关键结果与提示"
            self.summary = f"{self.title}：重点关注{step_text}，并确认{assertion_text}。"
        return self


class RequirementInput(BaseModel):
    id: str
    title: str
    markdown_content: str
    scenario_detail_level: ScenarioDetailLevel = ScenarioDetailLevel.STANDARD
    image_paths: list[str] = Field(default_factory=list)
    source: str = "manual"
    notes: str = ""
    business_level1_code: str = ""
    business_level1_name: str = ""
    business_level2_code: str = ""
    business_level2_name: str = ""
    created_at: datetime = Field(default_factory=now_utc)

    @property
    def business_path(self) -> str:
        level1 = self.business_level1_name or self.business_level1_code
        level2 = self.business_level2_name or self.business_level2_code
        if level1 and level2:
            return f"{level1} / {level2}"
        return level1 or ""


class TestAnalysisResult(BaseModel):
    requirement_id: str
    features: list[AnalysisFeature] = Field(default_factory=list)
    test_paths: list[TestPath] = Field(default_factory=list)
    scenarios: list[ScenarioDescriptor] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    summary: str = ""
    generated_at: datetime = Field(default_factory=now_utc)


class RequirementHandoffDecision(BaseModel):
    scenario_id: str
    status: ScenarioHandoffStatus = ScenarioHandoffStatus.AUTOMATION


class RequirementHandoff(BaseModel):
    requirement_id: str
    scenario_decisions: list[RequirementHandoffDecision] = Field(default_factory=list)
    selected_scenario_ids: list[str] = Field(default_factory=list)
    saved_at: datetime = Field(default_factory=now_utc)

    @property
    def automation_scenario_ids(self) -> list[str]:
        if self.scenario_decisions:
            return [
                item.scenario_id
                for item in self.scenario_decisions
                if item.status is ScenarioHandoffStatus.AUTOMATION
            ]
        return self.selected_scenario_ids


class RequirementRecordSummary(BaseModel):
    requirement_id: str
    title: str
    source: str = "manual"
    created_at: datetime
    generated_at: datetime | None = None
    summary: str = ""
    business_path: str = ""
    scenario_count: int = 0
    automation_count: int = 0
    regression_count: int = 0
    deferred_count: int = 0
    handoff_saved: bool = False


class RequirementRefinementRound(BaseModel):
    round_index: int
    user_input: str = ""
    analysis_summary: str = ""
    change_summary: str = ""
    created_at: datetime = Field(default_factory=now_utc)


class RequirementRecordDetail(BaseModel):
    requirement: RequirementInput
    analysis: TestAnalysisResult
    handoff: RequirementHandoff | None = None
    refinement_history: list[RequirementRefinementRound] = Field(default_factory=list)


class RequirementAnalysisDraft(BaseModel):
    requirement: RequirementInput
    latest_analysis: TestAnalysisResult | None = None
    current_handoff: RequirementHandoff | None = None
    refinement_history: list[RequirementRefinementRound] = Field(default_factory=list)
    source: RequirementDraftSource = RequirementDraftSource.NEW
    handoff_confirmed: bool = False
    last_updated_at: datetime = Field(default_factory=now_utc)


class CodegenTaskPack(BaseModel):
    requirement_id: str
    target_type: ScenarioType
    context_summary: str
    scenarios: list[ScenarioDescriptor] = Field(default_factory=list)
    coding_prompt: str
    acceptance_checks: list[str] = Field(default_factory=list)
    file_naming_rules: list[str] = Field(default_factory=list)


class RegressionSuggestion(BaseModel):
    scenario_id: str
    title: str
    module: str
    priority: str
    rationale: str
    recommended_scope: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class ExecutionArtifact(BaseModel):
    kind: str
    path: str
    description: str


class ExecutionRequest(BaseModel):
    request_id: str
    scenario_ids: list[str] = Field(default_factory=list)
    env_name: str = "test"
    trigger_reason: str = "manual"
    target_type: ScenarioType = ScenarioType.MIXED
    pytest_args: list[str] = Field(default_factory=list)
    dry_run: bool = False
    created_at: datetime = Field(default_factory=now_utc)


class ExecutionResult(BaseModel):
    request_id: str
    status: ExecutionStatus
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    summary: str = ""
    started_at: datetime = Field(default_factory=now_utc)
    finished_at: datetime = Field(default_factory=now_utc)
    stdout: str = ""
    stderr: str = ""
    artifacts: list[ExecutionArtifact] = Field(default_factory=list)
    failed_cases: list[str] = Field(default_factory=list)


class DefectDraft(BaseModel):
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


class LLMProbeReply(BaseModel):
    reply: str = Field(default="", description="模型探测请求返回的简短文本。")


class LLMConnectionTestResult(BaseModel):
    success: bool = False
    provider_model: str = ""
    base_url: str = ""
    live_mode_enabled: bool = False
    basic_connectivity_ok: bool = False
    structured_output_ok: bool = False
    message: str = ""
    response_excerpt: str = ""
    checked_at: datetime = Field(default_factory=now_utc)


class LLMCallLogEntry(BaseModel):
    occurred_at: datetime = Field(default_factory=now_utc)
    operation: str
    provider_model: str = ""
    base_url: str = ""
    success: bool = False
    used_fallback: bool = False
    live_mode_enabled: bool = False
    elapsed_ms: int = 0
    empty_output: bool = False
    fallback_reason: str = ""
    error_message: str = ""
    prompt_preview: str = ""
    response_preview: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class RuntimeLogEntry(BaseModel):
    occurred_at: datetime = Field(default_factory=now_utc)
    level: RuntimeLogLevel = RuntimeLogLevel.INFO
    event: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    traceback: str = ""
