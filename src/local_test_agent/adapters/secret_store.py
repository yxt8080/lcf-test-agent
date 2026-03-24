from __future__ import annotations

import json
import subprocess
from pathlib import Path


class SecretStore:
    """优先使用系统钥匙串，无法使用时退化到本地文件。

    本地单机工具不引入额外密钥基础设施，但仍要避免明文配置散落在普通设置文件中。
    """

    def __init__(self, fallback_file: Path, service_name: str = "local-test-agent") -> None:
        self.fallback_file = fallback_file
        self.service_name = service_name
        self.fallback_file.parent.mkdir(parents=True, exist_ok=True)

    def set_secret(self, key: str, value: str) -> None:
        if self._save_to_keychain(key, value):
            return
        payload = self._read_fallback()
        payload[key] = value
        self.fallback_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_secret(self, key: str) -> str:
        keychain_value = self._read_from_keychain(key)
        if keychain_value is not None:
            return keychain_value
        payload = self._read_fallback()
        return payload.get(key, "")

    def _save_to_keychain(self, key: str, value: str) -> bool:
        command = [
            "security",
            "add-generic-password",
            "-U",
            "-a",
            key,
            "-s",
            self.service_name,
            "-w",
            value,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    def _read_from_keychain(self, key: str) -> str | None:
        command = [
            "security",
            "find-generic-password",
            "-a",
            key,
            "-s",
            self.service_name,
            "-w",
        ]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            return completed.stdout.strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            return None

    def _read_fallback(self) -> dict[str, str]:
        if not self.fallback_file.exists():
            return {}
        return json.loads(self.fallback_file.read_text(encoding="utf-8"))

