# 测试规范

## 测试目标

本项目的测试重点不是覆盖所有 UI 细节，而是保证以下核心链路稳定：

- 需求分析结果可生成、可持久化
- 自动化任务包可生成
- 回归推荐能命中已有场景
- 测试执行结果能落库并生成报告
- 缺陷草稿能生成
- 统一配置读写不会破坏兼容性

## 测试分层

### 1. 单元/服务测试

适用对象：

- `store`
- `services`
- `controller`
- 各 Agent 的规则回退逻辑

要求：

- 优先覆盖纯 Python 逻辑
- 避免测试里依赖真实云效或真实模型

### 2. 集成测试

适用对象：

- 控制器到存储链路
- 配置仓库兼容读取
- 报告生成
- 缺陷草稿生成

要求：

- 使用临时目录
- 不污染真实本地配置和数据库

### 3. 桌面端基础校验

适用对象：

- 主窗口可初始化
- 页签可正常加载

要求：

- 使用 `QT_QPA_PLATFORM=offscreen`
- 不依赖人工点击

## 执行方式

运行全部测试：

```bash
./.venv/bin/pytest
```

运行单文件测试：

```bash
./.venv/bin/pytest tests/test_requirement_flow.py
```

桌面端离屏校验：

```bash
env QT_QPA_PLATFORM=offscreen ./.venv/bin/python -c "from pathlib import Path; from PySide6.QtWidgets import QApplication; from local_test_agent.bootstrap import build_controller; from local_test_agent.ui.main_window import MainWindow; app = QApplication([]); window = MainWindow(build_controller(Path.cwd())); print(window.windowTitle())"
```

## 编写测试时的约束

- 不要依赖真实网络请求
- 不要写入真实 `data/` 目录
- 不要把截图、数据库、报告等大文件提交到仓库
- 测试命名需表达业务语义，不要只写 `test_demo`

## 回归准则

以下变更必须补测试：

- 调整配置结构
- 调整数据库结构或写入逻辑
- 调整 Agent 输入输出模型
- 调整控制器公开接口
- 调整测试执行与报告生成流程

