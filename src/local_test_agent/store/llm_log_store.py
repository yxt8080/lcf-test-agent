from __future__ import annotations

import json
from pathlib import Path

from local_test_agent.models import LLMCallLogEntry


class LLMLogStore:
    """本地模型调用日志。

    需求分析、自动化设计等链路都可能在实时模型异常时退回规则模式，
    这里统一把调用阶段、耗时和错误原因落到本地文件，便于桌面端直接查看诊断信息。
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path

    def append(self, entry: LLMCallLogEntry) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def read_recent(self, limit: int = 100) -> list[LLMCallLogEntry]:
        if limit <= 0 or not self.log_path.exists():
            return []

        with self.log_path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()

        entries: list[LLMCallLogEntry] = []
        for line in lines[-limit:]:
            raw = line.strip()
            if not raw:
                continue
            try:
                entries.append(LLMCallLogEntry.model_validate_json(raw))
            except Exception:
                continue
        return list(reversed(entries))

    def clear(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")
