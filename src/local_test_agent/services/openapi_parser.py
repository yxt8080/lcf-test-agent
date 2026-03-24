from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from local_test_agent.services.runtime_logger import RuntimeLogger

try:
    import yaml
except ImportError:  # pragma: no cover - 依赖未安装时不走 YAML
    yaml = None


class OpenAPIParser:
    def __init__(self, runtime_logger: RuntimeLogger | None = None) -> None:
        self.runtime_logger = runtime_logger

    def parse(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "openapi.parse.start",
                "开始解析 OpenAPI 文档。",
                file_path=str(path),
                suffix=path.suffix.lower(),
            )
        try:
            if not path.exists():
                raise FileNotFoundError(f"未找到 OpenAPI 文档: {file_path}")
            if path.suffix.lower() in {".yaml", ".yml"}:
                if yaml is None:
                    raise RuntimeError("当前环境未安装 PyYAML，无法解析 YAML 文档。")
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
            summary = self._build_summary(payload)
            if self.runtime_logger is not None:
                self.runtime_logger.info(
                    "openapi.parse.success",
                    "OpenAPI 文档解析完成。",
                    file_path=str(path),
                    operation_count=summary.get("operation_count", 0),
                    title=summary.get("title", ""),
                )
            return summary
        except Exception:
            if self.runtime_logger is not None:
                self.runtime_logger.exception(
                    "openapi.parse.failed",
                    "OpenAPI 文档解析失败。",
                    file_path=str(path),
                )
            raise

    def _build_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        info = payload.get("info", {})
        operations: list[dict[str, Any]] = []
        for route, methods in payload.get("paths", {}).items():
            if not isinstance(methods, dict):
                continue
            for method, meta in methods.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue
                meta = meta or {}
                operations.append(
                    {
                        "operation_id": meta.get("operationId", f"{method}_{route}"),
                        "method": method.upper(),
                        "path": route,
                        "summary": meta.get("summary", ""),
                        "tags": meta.get("tags", []),
                        "request_body": bool(meta.get("requestBody")),
                        "response_codes": sorted((meta.get("responses") or {}).keys()),
                    }
                )
        return {
            "title": info.get("title", ""),
            "version": info.get("version", ""),
            "operation_count": len(operations),
            "operations": operations,
        }
