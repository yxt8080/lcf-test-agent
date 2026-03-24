from __future__ import annotations

import json
from pathlib import Path
from urllib import error, request

from local_test_agent.config import YunxiaoSettings
from local_test_agent.models import DefectDraft
from local_test_agent.services.runtime_logger import RuntimeLogger


class YunxiaoAdapter:
    """云效适配层。

    云效不同组织常见的差异在网关路径和字段映射，因此第一版保留路径与字段配置。
    如果未完成接口配置，则自动退化为本地草稿导出，避免误提单。
    """

    def __init__(
        self,
        settings: YunxiaoSettings,
        reports_dir: Path,
        runtime_logger: RuntimeLogger | None = None,
    ) -> None:
        self.settings = settings
        self.reports_dir = reports_dir
        self.runtime_logger = runtime_logger

    def submit_defect(self, draft: DefectDraft) -> str:
        if not self._is_remote_enabled():
            if self.runtime_logger is not None:
                self.runtime_logger.warning(
                    "yunxiao.submit.local_fallback",
                    "云效配置不完整，已退回本地草稿导出。",
                    request_id=draft.execution_request_id,
                )
            return self._save_local_submission(draft)
        payload = {
            "organizationId": self.settings.organization_id,
            "projectId": self.settings.project_id,
            "type": self.settings.defect_type,
            "title": draft.title,
            "description": draft.description,
            "reproSteps": draft.repro_steps,
            "expectedResult": draft.expected_result,
            "actualResult": draft.actual_result,
            "fields": draft.yunxiao_fields,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            url=f"{self.settings.api_base_url.rstrip('/')}{self.settings.create_defect_path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-accesstoken": self.settings.access_token,
            },
            method="POST",
        )
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "yunxiao.submit.remote_start",
                "开始调用云效提单接口。",
                request_id=draft.execution_request_id,
                api_base_url=self.settings.api_base_url,
                create_defect_path=self.settings.create_defect_path,
            )
        try:
            with request.urlopen(http_request, timeout=15) as response:
                content = json.loads(response.read().decode("utf-8") or "{}")
        except error.URLError as exc:  # pragma: no cover - 依赖真实接口
            if self.runtime_logger is not None:
                self.runtime_logger.exception(
                    "yunxiao.submit.remote_failed",
                    "云效提单接口调用失败。",
                    request_id=draft.execution_request_id,
                )
            raise RuntimeError(f"云效提单失败: {exc}") from exc
        defect_id = next(
            (
                str(value)
                for value in (
                    content.get("id"),
                    content.get("identifier"),
                    content.get("code"),
                )
                if value not in (None, "")
            ),
            "",
        )
        if not defect_id:
            if self.runtime_logger is not None:
                self.runtime_logger.error(
                    "yunxiao.submit.invalid_response",
                    "云效提单返回中缺少缺陷标识。",
                    request_id=draft.execution_request_id,
                    response_content=content,
                )
            raise RuntimeError(f"云效提单返回中未包含缺陷标识: {content}")
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "yunxiao.submit.remote_success",
                "云效缺陷已创建。",
                request_id=draft.execution_request_id,
                defect_id=defect_id,
            )
        return defect_id

    def _is_remote_enabled(self) -> bool:
        required = [
            self.settings.api_base_url,
            self.settings.organization_id,
            self.settings.project_id,
            self.settings.access_token,
        ]
        return all(required)

    def _save_local_submission(self, draft: DefectDraft) -> str:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        output = self.reports_dir / f"yunxiao-draft-{draft.execution_request_id}.json"
        output.write_text(
            draft.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return f"local-draft:{draft.execution_request_id}"
