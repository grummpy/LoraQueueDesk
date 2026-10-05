"""Opens a desk: config, client, lock, and the local queue."""

from __future__ import annotations

from typing import Any

from lora_queue_desk.comfy.errors import ComfyError
from lora_queue_desk.comfy.http import HttpComfyClient
from lora_queue_desk.comfy.mock import MockComfyClient
from lora_queue_desk.comfy.protocol import ComfyClient
from lora_queue_desk.config import Config
from lora_queue_desk.demo import demo_jobs
from lora_queue_desk.executor import ClientExecutor
from lora_queue_desk.lock import GamingLock
from lora_queue_desk.loras import classify_loras
from lora_queue_desk.models import DeskView, Job, JobState, LoraPack
from lora_queue_desk.queue import JobQueue
from lora_queue_desk.store import JsonJobStore


class Desk:
    def __init__(
        self,
        config: Config,
        client: ComfyClient,
        lock: GamingLock,
        store: JsonJobStore,
        queue: JobQueue,
    ) -> None:
        self.config = config
        self.client = client
        self.lock = lock
        self.store = store
        self.queue = queue

    @classmethod
    def open(cls, config: Config) -> Desk:
        config.data_dir.mkdir(parents=True, exist_ok=True)
        queue_name = "demo-queue.json" if config.demo else "queue.json"
        store = JsonJobStore(config.data_dir / queue_name)
        if config.demo and not store.path.exists():
            store.save(demo_jobs())
        jobs = store.load()
        client: ComfyClient
        if config.demo:
            client = MockComfyClient()
        else:
            client = HttpComfyClient(
                config.comfy_url,
                timeout=config.timeout,
                api_prefix=config.api_prefix,
            )
        lock = GamingLock(config.data_dir / "gaming.lock")
        queue = JobQueue(jobs, lock, ClientExecutor(client))
        return cls(config, client, lock, store, queue)

    @property
    def jobs(self) -> list[Job]:
        return self.queue.jobs

    def refresh(self) -> DeskView:
        paused = self.queue.apply_lock()
        if paused:
            self.store.save(self.jobs)
        return self.view()

    def view(self) -> DeskView:
        snapshot = self.lock.snapshot()
        error: str | None = None
        devices: list[str] = []
        installed: list[LoraPack] = []
        waiting: list[LoraPack] = []
        prompt_running: int | None = None
        prompt_pending: int | None = None
        try:
            health = self.client.health()
            devices = device_names(health)
            filenames = self.client.list_lora_files()
            installed, waiting = classify_loras(list(filenames), self.jobs)
            try:
                prompt_running, prompt_pending = prompt_counts(self.client.prompt_queue())
            except ComfyError:
                prompt_running = None
                prompt_pending = None
        except ComfyError as exc:
            error = str(exc)
        return DeskView(
            comfy_url=self.config.comfy_url,
            demo=self.config.demo,
            lock_on=snapshot.engaged,
            lock_sources=snapshot.sources,
            lock_path=str(snapshot.flag_path),
            jobs=tuple(self.jobs),
            installed=tuple(installed),
            waiting=tuple(waiting),
            comfy_error=error,
            devices=tuple(devices),
            prompt_running=prompt_running,
            prompt_pending=prompt_pending,
            demo_source=self.config.demo_source,
        )

    def set_lock(self, on: bool) -> tuple[DeskView, list[Job]]:
        if on:
            self.lock.engage()
            paused = self.queue.apply_lock()
        else:
            self.lock.release()
            paused = []
        self.store.save(self.jobs)
        return self.view(), paused

    def start(self, job_id: str | None) -> Job:
        self.queue.apply_lock()
        try:
            return self.queue.start(job_id)
        finally:
            self.store.save(self.jobs)

    def resume(self, job_id: str | None) -> Job:
        self.queue.apply_lock()
        try:
            return self.queue.resume(job_id)
        finally:
            self.store.save(self.jobs)

    def pause(self, job_id: str | None) -> list[Job]:
        paused = self.queue.pause(job_id)
        self.store.save(self.jobs)
        return paused

    def add_job(
        self,
        *,
        name: str,
        lora: str,
        rank: int | None,
        precision: str | None,
    ) -> Job:
        cleaned_name = name.strip()
        cleaned_lora = lora.strip()
        if not cleaned_name:
            raise ValueError("name is required")
        if not cleaned_lora:
            raise ValueError("lora is required")
        if rank is not None and rank < 1:
            raise ValueError("rank must be >= 1")
        cleaned_precision = precision.strip().upper() if precision and precision.strip() else None
        job = Job(
            id=new_job_id(cleaned_name, {item.id for item in self.jobs}),
            name=cleaned_name,
            state=JobState.WAITING,
            lora=cleaned_lora,
            rank=rank,
            precision=cleaned_precision,
            detail="Waiting for a free GPU",
        )
        self.queue.add(job)
        self.store.save(self.jobs)
        return job


def device_names(health: dict[str, Any]) -> list[str]:
    devices = health.get("devices") or []
    names: list[str] = []
    if not isinstance(devices, list):
        return names
    for device in devices:
        if isinstance(device, dict) and device.get("name"):
            names.append(str(device["name"]))
        elif isinstance(device, str):
            names.append(device)
    return names


def prompt_counts(payload: dict[str, Any]) -> tuple[int, int]:
    running = payload.get("queue_running") or []
    pending = payload.get("queue_pending") or []
    return (
        len(running) if isinstance(running, list) else 0,
        len(pending) if isinstance(pending, list) else 0,
    )


def new_job_id(name: str, existing: set[str]) -> str:
    slug = "".join(character.lower() if character.isalnum() else "-" for character in name)
    base = "-".join(part for part in slug.split("-") if part)[:24] or "job"
    if base not in existing:
        return base
    number = 2
    while f"{base}-{number}" in existing:
        number += 1
    return f"{base}-{number}"
