"""In-memory ComfyUI stand-in for demo mode and tests."""

from __future__ import annotations

from typing import Any, Mapping

from lora_queue_desk.comfy.errors import ComfyUnavailable
from lora_queue_desk.demo import DEMO_LORA_FILES


class MockComfyClient:
    def __init__(self, installed: list[str] | None = None, *, online: bool = True) -> None:
        self.installed = list(DEMO_LORA_FILES if installed is None else installed)
        self.online = online
        self.interrupts = 0
        self.submitted: list[dict[str, Any]] = []

    def health(self) -> dict[str, Any]:
        self._require_online()
        return {
            "system": {"os": "demo"},
            "devices": [
                {"name": "Mock GPU 0", "type": "mock"},
                {"name": "Mock GPU 1", "type": "mock"},
            ],
        }

    def list_lora_files(self) -> list[str]:
        self._require_online()
        return list(self.installed)

    def prompt_queue(self) -> dict[str, Any]:
        self._require_online()
        return {"queue_running": [], "queue_pending": []}

    def interrupt(self) -> None:
        self._require_online()
        self.interrupts += 1

    def submit_prompt(self, prompt: Mapping[str, Any], client_id: str | None = None) -> str:
        self._require_online()
        record = {"prompt": dict(prompt), "client_id": client_id}
        self.submitted.append(record)
        return f"demo-prompt-{len(self.submitted)}"

    def _require_online(self) -> None:
        if not self.online:
            raise ComfyUnavailable("Mock ComfyUI is offline")
