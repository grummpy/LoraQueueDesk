"""Structural type shared by the HTTP client and the mock client."""

from __future__ import annotations

from typing import Any, Mapping, Protocol


class ComfyClient(Protocol):
    def health(self) -> dict[str, Any]:
        """Return ``/system_stats`` or the mock equivalent."""

    def list_lora_files(self) -> list[str]:
        """Return LoRA filenames from ``/models/loras``."""

    def prompt_queue(self) -> dict[str, Any]:
        """Return the ComfyUI prompt queue (``queue_running`` and ``queue_pending``)."""

    def interrupt(self) -> None:
        """Ask the backend to stop the active prompt."""

    def submit_prompt(self, prompt: Mapping[str, Any], client_id: str | None = None) -> str:
        """Post a caller-built workflow. The desk does not call this on start."""
