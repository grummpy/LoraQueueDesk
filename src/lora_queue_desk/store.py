"""JSON persistence for the local job queue."""

from __future__ import annotations

import json
from pathlib import Path

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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"jobs": [job.to_dict() for job in jobs]}
        text = json.dumps(payload, indent=2) + "\n"
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(self.path)
