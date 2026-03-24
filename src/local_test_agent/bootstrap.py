from __future__ import annotations

from pathlib import Path

from local_test_agent.adapters.llm import LLMAdapter
from local_test_agent.adapters.yunxiao import YunxiaoAdapter
from local_test_agent.agents import (
    AutomationPlanningAgent,
    DefectDraftAgent,
    RegressionRoutingAgent,
    RequirementAnalysisAgent,
)
from local_test_agent.config import AppSettings
from local_test_agent.controller.workbench_controller import WorkbenchController
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


def build_controller(project_root: Path) -> WorkbenchController:
    config_store = ConfigStore(project_root)
    settings = config_store.load()
    settings.storage.app_dir.mkdir(parents=True, exist_ok=True)

    runtime_log_store = RuntimeLogStore(settings.storage.runtime_logs_path)
    runtime_logger = RuntimeLogger(runtime_log_store)
    database = LocalDatabase(settings.storage.database_path, runtime_logger=runtime_logger)
    llm_log_store = LLMLogStore(settings.storage.llm_logs_path)
    llm_adapter = LLMAdapter(settings.llm, log_store=llm_log_store)

    return WorkbenchController(
        settings=settings,
        config_store=config_store,
        database=database,
        llm_log_store=llm_log_store,
        runtime_log_store=runtime_log_store,
        runtime_logger=runtime_logger,
        requirement_agent=RequirementAnalysisAgent(llm_adapter),
        automation_agent=AutomationPlanningAgent(llm_adapter),
        regression_agent=RegressionRoutingAgent(llm_adapter),
        defect_agent=DefectDraftAgent(llm_adapter),
        openapi_parser=OpenAPIParser(runtime_logger=runtime_logger),
        scenario_index=ScenarioIndexService(database),
        artifact_collector=ArtifactCollector(settings.storage.artifacts_dir, runtime_logger=runtime_logger),
        report_builder=ReportBuilder(settings.storage.reports_dir, runtime_logger=runtime_logger),
        test_executor=TestExecutor(project_root, database, runtime_logger=runtime_logger),
        yunxiao_adapter=YunxiaoAdapter(
            settings.yunxiao,
            settings.storage.reports_dir,
            runtime_logger=runtime_logger,
        ),
    )
