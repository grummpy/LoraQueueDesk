"""JSON persistence for the local job queue."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import fcntl

from lora_queue_desk.models import Job


class StoreError(ValueError):
    """The queue file on disk cannot be read as jobs."""


class JsonJobStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Job]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"Queue file is not valid JSON: {self.path}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise StoreError(f"Queue file is missing a jobs list: {self.path}")
        jobs: list[Job] = []
        for item in data["jobs"]:
            try:
                jobs.append(Job.from_dict(item))
            except (TypeError, ValueError) as exc:
                raise StoreError(f"Queue file has an invalid job: {exc}") from exc
        return jobs

    def save(self, jobs: list[Job]) -> None:
        """Replace the queue while holding the per-queue mutation lock."""

        with self.mutation(jobs) as current:
            # ``save`` intentionally retains its replacement semantics for
            # bootstrap callers. Stateful desk commands use ``mutation`` to
            # reload before changing the queue instead.
            current[:] = jobs

    @contextmanager
    def mutation(self, fallback: list[Job]) -> Iterator[list[Job]]:
        """Serialize a local read-modify-write operation for this queue.

        A desk can remain open while another CLI process changes the same
        queue. Reloading inside the lock prevents either process from writing
        its stale in-memory snapshot over the other's update. The fallback is
        used only before a queue has ever been saved.
        """

        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                jobs = self.load() if self.path.exists() else fallback
                try:
                    yield jobs
                finally:
                    self._save_unlocked(jobs)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _save_unlocked(self, jobs: list[Job]) -> None:
        payload = {"jobs": [job.to_dict() for job in jobs]}
        text = json.dumps(payload, indent=2) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            # os.replace removes it on success; a failed write must not leave
            # a shared temporary name for another desk to mistake as state.
            temporary.unlink(missing_ok=True)
