from __future__ import annotations

from collections.abc import Mapping, Sequence
from traceback import format_exc
from typing import Any

from local_test_agent.models import RuntimeLogEntry, RuntimeLogLevel
from local_test_agent.store.runtime_log_store import RuntimeLogStore


class RuntimeLogger:
    """面向业务链路的轻量结构化日志入口。"""

    def __init__(self, store: RuntimeLogStore) -> None:
        self.store = store

    def info(self, event: str, message: str, **context: Any) -> None:
        self._append(RuntimeLogLevel.INFO, event, message, context=context)

    def warning(self, event: str, message: str, **context: Any) -> None:
        self._append(RuntimeLogLevel.WARNING, event, message, context=context)

    def error(self, event: str, message: str, **context: Any) -> None:
        self._append(RuntimeLogLevel.ERROR, event, message, context=context)

    def exception(self, event: str, message: str, **context: Any) -> None:
        self._append(
            RuntimeLogLevel.ERROR,
            event,
            message,
            context=context,
            traceback_text=format_exc().strip(),
        )

    def _append(
        self,
        level: RuntimeLogLevel,
        event: str,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        traceback_text: str = "",
    ) -> None:
        self.store.append(
            RuntimeLogEntry(
                level=level,
                event=event,
                message=message,
                context=self._normalize_mapping(context or {}),
                traceback=traceback_text[:4000],
            )
        )

    def _normalize_mapping(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if value in (None, "", [], {}, ()):
                continue
            normalized[str(key)] = self._normalize_value(value)
        return normalized

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return self._normalize_mapping(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [self._normalize_value(item) for item in value[:10]]
        if isinstance(value, str):
            normalized = value.strip()
            if len(normalized) <= 500:
                return normalized
            return f"{normalized[:500]}...(截断)"
        if isinstance(value, (int, float, bool)):
            return value
        return str(value)
