from __future__ import annotations

import json
from pathlib import Path

from local_test_agent.models import ExecutionArtifact, ExecutionRequest, ExecutionResult
from local_test_agent.services.runtime_logger import RuntimeLogger


class ArtifactCollector:
    def __init__(self, artifacts_dir: Path, runtime_logger: RuntimeLogger | None = None) -> None:
        self.artifacts_dir = artifacts_dir
        self.runtime_logger = runtime_logger
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def collect(
        self,
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> list[ExecutionArtifact]:
        run_dir = self.artifacts_dir / request.request_id
        run_dir.mkdir(parents=True, exist_ok=True)

        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"
        metadata_path = run_dir / "metadata.json"

        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(
                {
                    "request": request.model_dump(mode="json"),
                    "result": result.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "artifact.collect.success",
                "执行产物已归档。",
                request_id=request.request_id,
                run_dir=str(run_dir),
                artifact_count=3,
            )
        return [
            ExecutionArtifact(
                kind="stdout",
                path=str(stdout_path),
                description="pytest 标准输出",
            ),
            ExecutionArtifact(
                kind="stderr",
                path=str(stderr_path),
                description="pytest 错误输出",
            ),
            ExecutionArtifact(
                kind="metadata",
                path=str(metadata_path),
                description="执行元数据快照",
            ),
        ]
