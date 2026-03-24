from __future__ import annotations

from pathlib import Path

from local_test_agent.models import DefectDraft, ExecutionResult
from local_test_agent.services.runtime_logger import RuntimeLogger


class ReportBuilder:
    def __init__(self, reports_dir: Path, runtime_logger: RuntimeLogger | None = None) -> None:
        self.reports_dir = reports_dir
        self.runtime_logger = runtime_logger
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def build_execution_report(self, result: ExecutionResult) -> tuple[Path, Path]:
        markdown_path = self.reports_dir / f"{result.request_id}.md"
        html_path = self.reports_dir / f"{result.request_id}.html"

        markdown = self._build_markdown(result)
        html = self._build_html(result)

        markdown_path.write_text(markdown, encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "report.execution.write",
                "执行报告文件已写入。",
                request_id=result.request_id,
                markdown_path=str(markdown_path),
                html_path=str(html_path),
            )
        return markdown_path, html_path

    def build_defect_preview(self, draft: DefectDraft) -> Path:
        preview_path = self.reports_dir / f"defect-{draft.execution_request_id}.md"
        preview = "\n".join(
            [
                f"# {draft.title}",
                "",
                "## 描述",
                draft.description,
                "",
                "## 复现步骤",
                *[f"{index}. {step}" for index, step in enumerate(draft.repro_steps, start=1)],
                "",
                "## 期望结果",
                draft.expected_result,
                "",
                "## 实际结果",
                draft.actual_result,
                "",
                "## 附件",
                *[f"- {item}" for item in draft.attachments],
            ]
        )
        preview_path.write_text(preview, encoding="utf-8")
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "report.defect_preview.write",
                "缺陷预览文件已写入。",
                request_id=draft.execution_request_id,
                preview_path=str(preview_path),
            )
        return preview_path

    def _build_markdown(self, result: ExecutionResult) -> str:
        lines = [
            f"# 测试执行报告 {result.request_id}",
            "",
            f"- 状态: {result.status.value}",
            f"- 总数: {result.total}",
            f"- 通过: {result.passed}",
            f"- 失败: {result.failed}",
            f"- 跳过: {result.skipped}",
            "",
            "## 摘要",
            result.summary,
            "",
            "## 失败用例",
        ]
        if result.failed_cases:
            lines.extend(f"- {case}" for case in result.failed_cases)
        else:
            lines.append("- 无")
        lines.extend(["", "## 产物"])
        if result.artifacts:
            lines.extend(f"- {artifact.kind}: {artifact.path}" for artifact in result.artifacts)
        else:
            lines.append("- 无")
        return "\n".join(lines)

    def _build_html(self, result: ExecutionResult) -> str:
        artifacts = "".join(
            f"<li><strong>{artifact.kind}</strong>: {artifact.path}</li>"
            for artifact in result.artifacts
        ) or "<li>无</li>"
        failed_cases = "".join(f"<li>{case}</li>" for case in result.failed_cases) or "<li>无</li>"
        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>测试执行报告 {result.request_id}</title>
  <style>
    body {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; margin: 32px; color: #1f2937; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .card {{ border: 1px solid #dbe4f0; border-radius: 12px; padding: 16px; background: #f8fbff; }}
    h1, h2 {{ color: #0f172a; }}
  </style>
</head>
<body>
  <h1>测试执行报告 {result.request_id}</h1>
  <div class="grid">
    <div class="card">状态：{result.status.value}</div>
    <div class="card">总数：{result.total}</div>
    <div class="card">通过：{result.passed}</div>
    <div class="card">失败：{result.failed}</div>
  </div>
  <h2>摘要</h2>
  <p>{result.summary}</p>
  <h2>失败用例</h2>
  <ul>{failed_cases}</ul>
  <h2>产物</h2>
  <ul>{artifacts}</ul>
</body>
</html>
""".strip()
