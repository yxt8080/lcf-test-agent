from __future__ import annotations

import json
from pathlib import Path

from local_test_agent.models import RuntimeLogEntry


class RuntimeLogStore:
    """统一保存运行期结构化事件。

    LLM 调用日志主要用于分析模型行为；这里额外记录 controller、service、
    adapter 和 UI worker 的运行事件，方便按链路复盘本地工作台的真实执行过程。
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path

    def append(self, entry: RuntimeLogEntry) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def read_recent(self, limit: int = 100) -> list[RuntimeLogEntry]:
        if limit <= 0 or not self.log_path.exists():
            return []

        with self.log_path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()

        entries: list[RuntimeLogEntry] = []
        for line in lines[-limit:]:
            raw = line.strip()
            if not raw:
                continue
            try:
                entries.append(RuntimeLogEntry.model_validate_json(raw))
            except Exception:
                continue
        return list(reversed(entries))

    def clear(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")
