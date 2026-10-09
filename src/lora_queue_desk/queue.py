"""Local job queue. The gaming lock is enforced here, not in the HTTP client."""

from __future__ import annotations

from lora_queue_desk.executor import Executor
from lora_queue_desk.lock import GamingLock, LockEngagedError
from lora_queue_desk.models import Job, JobState


class JobQueue:
    def __init__(self, jobs: list[Job], lock: GamingLock, executor: Executor) -> None:
        self.jobs = jobs
        self.lock = lock
        self.executor = executor

    def add(self, job: Job) -> Job:
        self.jobs.append(job)
        return job

    def apply_lock(self) -> list[Job]:
        """Pause every running job when the lock is engaged. No-op when it is clear."""

        if not self.lock.snapshot().engaged:
            return []
        paused: list[Job] = []
        for job in self.jobs:
            if job.state is JobState.RUNNING:
                if self._mark_paused(job, by_lock=True):
                    paused.append(job)
        return paused

    def start(self, job_id: str | None = None) -> Job:
        self._ensure_unlocked("start")
        job = self._pick_waiting(job_id)
        if job.state is JobState.RUNNING:
            return job
        self._activate(job)
        return job

    def resume(self, job_id: str | None = None) -> Job:
        self._ensure_unlocked("resume")
        job = self._pick_paused(job_id)
        if job.state is JobState.WAITING:
            self._activate(job)
            return job
        if job.state is JobState.RUNNING:
            return job
        self._activate(job)
        return job

    def pause(self, job_id: str | None = None) -> list[Job]:
        if job_id is None:
            targets = [job for job in self.jobs if job.state is JobState.RUNNING]
            if not targets:
                raise ValueError("No running jobs")
        else:
            job = self._require(job_id)
            if job.state is JobState.PAUSED:
                return [job]
            if job.state is not JobState.RUNNING:
                raise ValueError(f"{job.name} is {job.state.value}, not running")
            targets = [job]
        for job in targets:
            self._mark_paused(job, by_lock=False)
        return [job for job in targets if job.state is JobState.PAUSED]

    def _activate(self, job: Job) -> None:
        self.executor.start(job)
        if not job.gpu:
            job.gpu = self._free_gpu()
        job.state = JobState.RUNNING
        job.paused_by_lock = False
        job.detail = f"Running on {job.gpu}"

    def _mark_paused(self, job: Job, *, by_lock: bool) -> bool:
        if job.state is JobState.RUNNING:
            try:
                self.executor.interrupt(job)
            except Exception as exc:
                # We cannot truthfully report a stopped GPU after the only
                # stop request failed. Keep the observed running state while
                # the lock still fail-closes future starts and resumes.
                job.detail = f"Still running; backend interrupt failed: {exc}"
                return False
            else:
                job.detail = "Paused by gaming lock" if by_lock else "Paused"
        job.state = JobState.PAUSED
        job.paused_by_lock = True if by_lock else False
        return True

    def _ensure_unlocked(self, action: str) -> None:
        snapshot = self.lock.snapshot()
        if snapshot.engaged:
            raise LockEngagedError(action, snapshot)

    def _pick_waiting(self, job_id: str | None) -> Job:
        if job_id is None:
            waiting = [job for job in self.jobs if job.state is JobState.WAITING]
            if not waiting:
                raise ValueError("No waiting jobs")
            return waiting[0]
        job = self._require(job_id)
        if job.state is JobState.RUNNING:
            return job
        if job.state is JobState.PAUSED:
            raise ValueError(f"{job.name} is paused. Use resume once the gaming lock is off.")
        if job.state is not JobState.WAITING:
            raise ValueError(f"{job.name} is {job.state.value}")
        return job

    def _pick_paused(self, job_id: str | None) -> Job:
        if job_id is None:
            paused = [job for job in self.jobs if job.state is JobState.PAUSED]
            if not paused:
                raise ValueError("No paused jobs")
            held = [job for job in paused if job.paused_by_lock]
            return (held or paused)[0]
        job = self._require(job_id)
        if job.state is JobState.RUNNING:
            return job
        if job.state is JobState.WAITING:
            return job
        if job.state is not JobState.PAUSED:
            raise ValueError(f"{job.name} is {job.state.value}")
        return job

    def _require(self, job_id: str) -> Job:
        for job in self.jobs:
            if job.id == job_id:
                return job
        raise ValueError(f"Unknown job {job_id}")

    def _free_gpu(self) -> str:
        used = {job.gpu for job in self.jobs if job.state is JobState.RUNNING and job.gpu}
        for index in range(8):
            slot = f"GPU {index}"
            if slot not in used:
                return slot
        return "GPU 0"
