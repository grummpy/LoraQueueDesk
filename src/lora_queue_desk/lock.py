"""Gaming / presence lock.

The queue will not start or resume GPU work while this lock is engaged.
Engaging it also pauses jobs that are already running.

Any one of these sources engages the lock:

* a flag file (``lora-queue lock on`` writes it; ``lock off`` deletes it)
* ``LORA_QUEUE_GAMING_LOCK`` or ``LORA_QUEUE_PRESENCE_LOCK`` set to
  on / true / yes / 1
* a :class:`PresenceDetector` that reports gaming or projection

``lock off`` only removes the flag file. An environment variable or a
detector that still reports active keeps the lock on. Releasing the lock
does not resume jobs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

TRUTHY = frozenset({"1", "true", "yes", "on"})
FALSY = frozenset({"0", "false", "no", "off"})
ENV_KEYS = ("LORA_QUEUE_GAMING_LOCK", "LORA_QUEUE_PRESENCE_LOCK")


class PresenceDetector(Protocol):
    def gaming_or_projection_active(self) -> bool:
        """Return True when a game or a projection session should keep the GPU free."""


class NullPresenceDetector:
    """Built-in detector. It always reports clear.

    Replace this with a process list, a window title, or a hardware switch
    later. The queue only calls ``gaming_or_projection_active``.
    """

    def gaming_or_projection_active(self) -> bool:
        return False


@dataclass(frozen=True)
class LockSnapshot:
    engaged: bool
    sources: tuple[str, ...]
    flag_path: Path


class LockEngagedError(RuntimeError):
    """A start or resume was refused because the gaming lock is on."""

    def __init__(self, action: str, snapshot: LockSnapshot) -> None:
        self.action = action
        self.snapshot = snapshot
        sources = ", ".join(snapshot.sources) or "unknown"
        super().__init__(
            f"Refusing to {action}: gaming lock is on ({sources}). "
            f"Flag file: {snapshot.flag_path}. "
            "Turn the file flag off with `lora-queue lock off`. "
            "That does not resume jobs, and it does not unset "
            "LORA_QUEUE_GAMING_LOCK or LORA_QUEUE_PRESENCE_LOCK."
        )


class GamingLock:
    """File, environment, and detector combined. Also called a presence lock."""

    def __init__(
        self,
        flag_path: Path,
        *,
        environ: Mapping[str, str] | None = None,
        detector: PresenceDetector | None = None,
    ) -> None:
        self.flag_path = flag_path
        self.environ = os.environ if environ is None else environ
        self.detector = detector if detector is not None else NullPresenceDetector()

    def snapshot(self) -> LockSnapshot:
        sources: list[str] = []
        if self._file_engaged():
            sources.append("file")
        if self._env_engaged():
            sources.append("env")
        self._collect_detector(sources)
        return LockSnapshot(engaged=bool(sources), sources=tuple(sources), flag_path=self.flag_path)

    def engage(self) -> None:
        self.flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.flag_path.write_text("on\n", encoding="utf-8")

    def release(self) -> None:
        if self.flag_path.exists():
            self.flag_path.unlink()

    def _file_engaged(self) -> bool:
        if not self.flag_path.exists():
            return False
        text = self.flag_path.read_text(encoding="utf-8").strip().lower()
        if text in FALSY:
            return False
        return True

    def _env_engaged(self) -> bool:
        for key in ENV_KEYS:
            raw = self.environ.get(key)
            if raw is None:
                continue
            if raw.strip().lower() in TRUTHY:
                return True
        return False

    def _collect_detector(self, sources: list[str]) -> None:
        try:
            active = bool(self.detector.gaming_or_projection_active())
        except Exception:
            sources.append("detector-error")
            return
        if active:
            sources.append("detector")
