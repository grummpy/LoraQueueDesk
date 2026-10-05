"""Shared records for jobs, packs, and a desk snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class JobState(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class Job:
    id: str
    name: str
    state: JobState
    lora: str
    rank: int | None = None
    precision: str | None = None
    progress: float = 0.0
    gpu: str | None = None
    paused_by_lock: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.value,
            "lora": self.lora,
            "rank": self.rank,
            "precision": self.precision,
            "progress": self.progress,
            "gpu": self.gpu,
            "paused_by_lock": self.paused_by_lock,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        if not isinstance(data, dict):
            raise TypeError("job entry must be an object")
        try:
            rank = data.get("rank")
            return cls(
                id=str(data["id"]),
                name=str(data["name"]),
                state=JobState(str(data["state"])),
                lora=str(data["lora"]),
                rank=None if rank is None else int(rank),
                precision=None if data.get("precision") is None else str(data["precision"]),
                progress=float(data.get("progress") or 0),
                gpu=None if data.get("gpu") is None else str(data["gpu"]),
                paused_by_lock=bool(data.get("paused_by_lock")),
                detail=str(data.get("detail") or ""),
            )
        except KeyError as exc:
            raise ValueError(f"job is missing {exc.args[0]}") from exc


@dataclass(frozen=True)
class LoraPack:
    name: str
    installed: bool
    filename: str | None = None


@dataclass(frozen=True)
class DeskView:
    comfy_url: str
    demo: bool
    lock_on: bool
    lock_sources: tuple[str, ...]
    lock_path: str
    jobs: tuple[Job, ...]
    installed: tuple[LoraPack, ...]
    waiting: tuple[LoraPack, ...]
    comfy_error: str | None
    devices: tuple[str, ...]
    prompt_running: int | None
    prompt_pending: int | None
