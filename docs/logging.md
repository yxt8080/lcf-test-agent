# 日志规范

## 目标

本规范用于约束本项目后续新增代码、重构代码和自动生成代码的日志写法，目标是保证：

- 同一条工作流可以按时间顺序复盘
- 模型行为与业务链路可以关联排查
- 异常、降级、回退路径不会静默发生
- 日志字段稳定，便于后续过滤、统计和代码生成复用

本项目当前日志分为两类：

- `LLM` 调用日志：落盘到 `data/llm_calls.log`
- 运行日志：落盘到 `data/runtime_events.log`

## 总体原则

### 1. 先结构化，后描述性

日志优先记录稳定字段，不要只写一段自然语言。

推荐：

- `event="execution.run.success"`
- `context={"request_id": "...", "artifact_count": 3}`

不推荐：

- `"执行完成了，结果还可以"`

### 2. 一条公开链路至少有起止日志

以下入口必须至少记录：

- `start`
- `success`
- `failed`

适用范围：

- `controller` 对外公开方法
- 长耗时 `service`
- 外部系统 `adapter`
- 后台线程任务

### 3. 降级和回退必须显式可见

以下情况不能静默发生，必须落日志：

- 实时模型退回规则模式
- 云效退回本地草稿
- `FTS5` 检索退回 `LIKE`
- `dry-run`
- 依赖缺失导致流程阻断

### 4. 业务主键优先进入上下文

日志上下文优先放稳定关联键，便于跨文件、跨阶段串联：

- `requirement_id`
- `request_id`
- `scenario_id`
- `target_type`
- `environment`
- `provider_model`
- `refinement_round`

### 5. 禁止记录敏感原文

以下内容禁止写入日志：

- `API Key`
- `Token`
- 密码
- Cookie
- 完整鉴权请求头
- 用户敏感输入原文

如果必须记录，只能写脱敏值、长度、是否存在这类摘要信息。

## 日志类型约束

### 1. 运行日志

统一使用 `RuntimeLogger`。

适用场景：

- controller 工作流
- service 执行链路
- adapter 外部调用
- worker 异步任务
- 数据库降级与兼容分支

字段约束：

- `level`: `info` / `warning` / `error`
- `event`: 稳定事件名，必须可枚举、可搜索
- `message`: 面向人工阅读的简短说明
- `context`: 结构化上下文
- `traceback`: 仅异常场景记录

### 2. LLM 调用日志

统一通过 `LLMAdapter.log_call(...)` 记录。

适用场景：

- Agent 结构化调用
- LLM 配置连通性测试
- 模型结构化输出失败
- 模型异常后回退规则模式

字段约束：

- 必须记录 `operation`
- 必须记录 `success`
- 必须记录 `used_fallback`
- 必须记录 `context`
- `prompt_preview` 和 `response_preview` 只保留摘要，不保留整段原文

## 事件命名规范

### 1. 命名格式

统一使用：

```text
<domain>.<action>.<stage>
```

示例：

- `requirement.analysis.start`
- `requirement.analysis.success`
- `requirement.analysis.failed`
- `pytest.execute.prepare`
- `pytest.execute.complete`
- `yunxiao.submit.local_fallback`

### 2. 域名约束

优先使用以下领域前缀：

- `requirement`
- `automation`
- `regression`
- `execution`
- `pytest`
- `artifact`
- `report`
- `defect`
- `settings`
- `worker`
- `database`
- `openapi`
- `yunxiao`
- `logs`

不要使用过于泛化的前缀，例如：

- `task.*`
- `job.*`
- `misc.*`

### 3. 阶段命名约束

优先复用以下后缀：

- `start`
- `prepare`
- `success`
- `complete`
- `failed`
- `blocked`
- `local_fallback`

不要为相同语义发明多个近义词，例如不要同时出现：

- `finish`
- `done`
- `complete`

应统一选一个。

## 不同分层的打点要求

### 1. Controller

要求：

- 每个公开工作流方法必须记录 `start/success/failed`
- `success` 日志必须包含关键结果计数
- `failed` 日志必须使用 `exception(...)`

最少上下文字段：

- 输入主键
- 场景数量、结果数量、附件数量等计数
- 目标类型、环境等关键执行参数

### 2. Service

要求：

- 长耗时操作必须记录开始和完成
- 命令行执行必须记录真实命令
- 降级分支必须记录 `warning`

示例：

- `pytest.execute.start`
- `pytest.execute.complete`
- `database.scenario_search.fallback`

### 3. Adapter

要求：

- 外部请求前记录目标系统和关键路径
- 外部失败记录 `exception`
- 本地回退记录 `warning`
- 禁止记录敏感请求头原文

### 4. Worker

要求：

- 任务提交时记录 `submit`
- 完成时记录 `success`
- 异常时记录 `failed`
- 异常必须保留 traceback

### 5. Agent / LLM

要求：

- 所有结构化模型调用都要写 `LLM` 日志
- 若业务链路可识别，必须补 `context`
- 回退原因必须可枚举，不要只写自然语言

推荐回退原因：

- `live_llm_disabled_or_dependency_missing`
- `empty_structured_output`
- `agent_exception`
- `requirement_analysis_missing_features`

## context 字段规范

### 1. 必须是稳定 JSON 结构

`context` 只允许放可稳定序列化、可过滤的内容：

- 字符串
- 数字
- 布尔值
- 小型数组
- 小型对象

### 2. 推荐字段

优先使用：

- `requirement_id`
- `request_id`
- `scenario_count`
- `candidate_count`
- `artifact_count`
- `failed_case_count`
- `target_type`
- `environment`
- `provider_model`
- `operation_count`

### 3. 不要放大对象原文

禁止直接塞入：

- 完整 `Pydantic` 模型
- 完整 `stdout/stderr`
- 完整需求正文
- 完整 OpenAPI 文档

正确做法是改成摘要字段，例如：

- `scenario_count`
- `bug_description_length`
- `openapi_operation_count`
- `has_openapi=True`

## 异常日志规范

### 1. 能保留栈时必须保留栈

如果当前代码在 `except` 代码块中，优先使用：

```python
runtime_logger.exception("worker.task.failed", "后台任务执行失败。", worker_fn="demo")
```

不要只写：

```python
runtime_logger.error("worker.task.failed", "后台任务执行失败。", error_message=str(exc))
```

### 2. 用户可预期校验失败不强制记录 error

例如：

- 表单为空
- 用户未选择需求记录
- 场景状态未填全

这类可直接返回业务错误，不一定需要写运行日志；但如果它会导致链路中断且后续难排查，可以补 `warning`。

## 日志内容边界

### 应记录

- 事件名
- 关键主键
- 关键数量
- 是否走回退/降级
- 外部调用目标
- 执行耗时
- 异常栈

### 不应记录

- 密钥
- 完整超长正文
- 重复的大段 `stdout`
- 无法稳定过滤的情绪化描述

## 代码生成模板

### 1. Controller 模板

```python
self.runtime_logger.info(
    "automation.plan.start",
    "开始生成自动化任务包。",
    requirement_id=requirement_id,
    target_type=target_type,
)
try:
    result = self.some_service.run(...)
    self.runtime_logger.info(
        "automation.plan.success",
        "自动化任务包生成完成。",
        requirement_id=requirement_id,
        scenario_count=len(result.scenarios),
    )
    return result
except Exception:
    self.runtime_logger.exception(
        "automation.plan.failed",
        "自动化任务包生成失败。",
        requirement_id=requirement_id,
        target_type=target_type,
    )
    raise
```

### 2. Service 模板

```python
if self.runtime_logger is not None:
    self.runtime_logger.info(
        "pytest.execute.start",
        "开始调用 pytest。",
        request_id=request.request_id,
        command=command,
    )
```

### 3. 回退模板

```python
if self.runtime_logger is not None:
    self.runtime_logger.warning(
        "yunxiao.submit.local_fallback",
        "云效配置不完整，已退回本地草稿导出。",
        request_id=draft.execution_request_id,
    )
```

### 4. LLM 模板

```python
payload = self.run_structured(
    prompt,
    fallback,
    log_context={
        "requirement_id": requirement.id,
        "scenario_detail_level": requirement.scenario_detail_level.value,
        "refinement_round": len(refinement_history or []),
    },
)
```

## 新代码的检查清单

后续新增代码时，提交前至少自查以下问题：

1. 这个公开链路是否有 `start/success/failed`？
2. 这个异常是否保留了 traceback？
3. 这个降级是否是显式可见的？
4. `context` 是否包含主键和数量字段？
5. 是否误记了敏感信息？
6. 事件命名是否符合 `<domain>.<action>.<stage>`？
7. 同类代码是否复用了现有事件前缀，而不是重新发明？

## 建议的后续使用方式

后续给代码生成模型下指令时，建议直接附加一句：

```text
请严格遵守 docs/logging.md 中的日志规范，新增公开工作流必须补 start/success/failed 日志，异常必须保留 traceback，降级路径必须显式 warning。
```

这样生成结果会比只说“补日志”稳定很多。
