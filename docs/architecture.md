# 架构说明

## 总览

本项目采用“**普通 Python 工作流编排 + 有限使用 PydanticAI**”的架构，优先解决本地测试工作台的稳定性与可维护性问题。

```text
UI(Page)
  -> Controller
    -> Agents / Services / Adapters / Store
```

## 分层职责

### UI

位置：`src/local_test_agent/ui/`

职责：

- 展示页面
- 收集输入
- 调用后台 worker
- 渲染结构化输出

约束：

- 不直接访问数据库
- 不直接请求外部平台
- 不承担业务推理

### Controller

位置：`src/local_test_agent/controller/`

职责：

- 聚合工作流步骤
- 协调 Agent、Service、Store、Adapter
- 对 UI 暴露稳定接口

约束：

- 不实现复杂智能逻辑
- 不直接包含第三方 API 细节

### Agents

位置：`src/local_test_agent/agents/`

当前实现：

- `RequirementAnalysisAgent`
- `AutomationPlanningAgent`
- `RegressionRoutingAgent`
- `DefectDraftAgent`

职责：

- 将输入转为结构化推理结果
- 负责测试分析、任务包生成、回归推荐、缺陷草稿生成

约束：

- 输出必须是 Pydantic 模型
- 模型不可用时允许回退到规则模式

### Services

位置：`src/local_test_agent/services/`

职责：

- `OpenAPIParser`：解析 Swagger/OpenAPI 文档
- `ScenarioIndexService`：检索已保存场景
- `TestExecutor`：本地执行 pytest
- `ArtifactCollector`：归档执行产物
- `ReportBuilder`：生成测试报告和缺陷预览

### Adapters

位置：`src/local_test_agent/adapters/`

职责：

- `LLMAdapter`：封装 PydanticAI / OpenAI 兼容模型
- `YunxiaoAdapter`：封装云效缺陷接口
- `SecretStore`：封装本机安全存储

### Store

位置：`src/local_test_agent/store/`

职责：

- `LocalDatabase`：SQLite 持久化
- `ConfigStore`：统一配置读写

## 配置设计

- 主配置文件：`data/app_config.json`
- 敏感信息：系统钥匙串优先；不可用时退化到本地密钥文件
- 所有路径都按项目根目录解析，避免不同启动方式导致相对路径漂移

## 关键工作流

### 需求分析

`UI -> Controller.analyze_requirement -> RequirementAnalysisAgent -> SQLite`

### 自动化设计

`UI -> Controller.plan_automation -> OpenAPIParser + AutomationPlanningAgent`

### 回归推荐

`UI -> Controller.recommend_regression -> ScenarioIndexService -> RegressionRoutingAgent`

### 执行与报告

`UI -> Controller.run_tests -> TestExecutor -> ArtifactCollector -> SQLite`

### 缺陷草稿

`UI -> Controller.build_defect_draft -> DefectDraftAgent -> ReportBuilder -> YunxiaoAdapter`

## 设计取舍

- 不采用“大总控 Agent”，避免调试困难
- 不做远程服务，降低部署和账号体系复杂度
- 不在第一版直接调用 Codex/Claude API，而是输出规范化提示词
- 缺陷提单必须人工确认，优先控制误报风险

