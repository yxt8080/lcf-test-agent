# Contributing Guide

## 适用范围

本项目目前主要供个人维护，但仍按可持续演进方式管理代码。以下约定用于约束后续迭代，避免本地工具逐步失控。

## 本地开发

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python main.py
```

一键启动：

```bash
./scripts/start.sh
```

## 开发流程

1. 先确认改动属于哪一层：`ui / controller / agents / services / adapters / store`
2. 如涉及新增数据结构，先补 Pydantic 模型
3. 如涉及外部平台接入，先新增 adapter，不要直接在 controller 或 page 中写请求
4. 完成代码后补最小必要测试
5. 运行测试并确认启动不报错

## 代码风格

- 4 空格缩进
- 公共函数和复杂逻辑需要简洁中文注释
- 变量名与函数名使用清晰英文；注释说明业务语义
- 优先拆小函数，不要在页面类中堆长函数
- 对用户可见的错误，返回明确中文提示

## Agent 开发规范

- Agent 只负责“理解、归纳、排序、生成结构化结果”
- Agent 输出必须是确定结构，不允许只返回自由文本
- Agent 失败时必须有本地回退或可解释错误
- 不将 OpenAPI 解析、pytest 执行、文件写入等工程能力塞进 Agent

## 配置与安全

- 统一配置文件：`data/app_config.json`
- 敏感信息：通过 `SecretStore` 管理
- 文档、测试样例与截图中不得包含真实生产数据

## 测试要求

运行全部测试：

```bash
./.venv/bin/pytest
```

运行离屏桌面初始化验证：

```bash
env QT_QPA_PLATFORM=offscreen ./.venv/bin/python -c "from pathlib import Path; from PySide6.QtWidgets import QApplication; from local_test_agent.bootstrap import build_controller; from local_test_agent.ui.main_window import MainWindow; app = QApplication([]); window = MainWindow(build_controller(Path.cwd())); print(window.windowTitle())"
```

## 文档要求

以下变更必须同步更新文档：

- 调整目录结构
- 调整配置文件字段
- 调整工作流入口
- 增加新的外部平台接入
- 调整测试或提单流程

