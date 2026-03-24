# 本地测试智能体

一个仅供个人本机使用的测试工作台，覆盖以下流程：

- 导入需求文档和截图，生成测试范围、测试路径、风险点与建议场景
- 读取页面说明与 OpenAPI 文档，生成 UI/API 自动化开发提示词
- 根据 bug 描述推荐回归场景
- 执行本地测试，收集证据，生成测试报告与云效缺陷草稿

## 技术栈

- Python
- PySide6
- Pydantic / PydanticAI
- pytest
- Playwright
- httpx
- SQLite

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
.venv/bin/python main.py
```

如果你希望一键启动，可以直接执行：

```bash
./scripts/start.sh
```

在 macOS Finder 中也可以双击项目根目录下的 `start.command`。

如果尚未配置模型或云效参数，系统会自动退化到本地规则模式，便于先打通工作流。

## 目录结构

```text
src/local_test_agent/
  adapters/     外部系统适配
  agents/       PydanticAI 智能体
  controller/   页面事件与工作流编排
  models/       结构化数据模型
  services/     非 Agent 服务
  store/        SQLite 持久化
  ui/           PySide6 界面
```

## 配置说明

首次启动后，可在“设置”页配置：

- Azure/OpenAI 兼容模型地址、模型名、API Key
- 云效 API 地址、项目标识、令牌、缺陷接口路径
- 本地数据目录、报告目录、证据目录

统一配置文件默认位于 `data/app_config.json`。
其中敏感凭证仍优先保存在系统钥匙串；如果系统钥匙串不可用，则退化到本地密钥文件。

## 当前约束

- 第一版只支持本机单用户、单项目
- 缺陷提单前必须人工确认
- 截图只作为辅助理解，不能替代真实页面和接口文档
- 自动化代码生成阶段只输出规范化提示词，不直接改业务仓库

## 项目规范

- 开发约束见 [AGENTS.md](/Users/nyz/PyCharmMiscProject/agent/lcf-test-agent/AGENTS.md)
- 贡献与提交流程见 [CONTRIBUTING.md](/Users/nyz/PyCharmMiscProject/agent/lcf-test-agent/CONTRIBUTING.md)
- 架构说明见 [docs/architecture.md](/Users/nyz/PyCharmMiscProject/agent/lcf-test-agent/docs/architecture.md)
- 日志规范见 [docs/logging.md](/Users/nyz/PyCharmMiscProject/agent/lcf-test-agent/docs/logging.md)
- 测试规范见 [docs/testing.md](/Users/nyz/PyCharmMiscProject/agent/lcf-test-agent/docs/testing.md)
