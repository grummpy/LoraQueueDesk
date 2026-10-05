from pathlib import Path

import pytest

from lora_queue_desk.lock import GamingLock, LockEngagedError
from lora_queue_desk.models import Job, JobState
from lora_queue_desk.queue import JobQueue
from tests.fakes import RecordingExecutor


def _job(job_id: str, state: JobState, **kwargs: object) -> Job:
    return Job(id=job_id, name=job_id, state=state, lora=job_id, **kwargs)  # type: ignore[arg-type]


def test_start_and_resume_are_blocked_while_locked(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    lock = GamingLock(tmp_path / "gaming.lock")
    waiting = _job("icon-sheet", JobState.WAITING)
    paused = _job("rpg-avatars", JobState.PAUSED, paused_by_lock=True, gpu="GPU 0")
    queue = JobQueue([waiting, paused], lock, executor)

    lock.engage()
    with pytest.raises(LockEngagedError, match="Refusing to start"):
        queue.start()
    with pytest.raises(LockEngagedError, match="Refusing to resume"):
        queue.resume("rpg-avatars")

    assert waiting.state is JobState.WAITING
    assert paused.state is JobState.PAUSED
    assert executor.started == []
    assert executor.interrupted == []


def test_lock_pauses_running_work_and_release_does_not_resume(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    lock = GamingLock(tmp_path / "gaming.lock")
    running = _job("texture-upscaler", JobState.RUNNING, gpu="GPU 1", progress=28)
    queue = JobQueue([running], lock, executor)

    lock.engage()
    paused = queue.apply_lock()
    assert paused == [running]
    assert running.state is JobState.PAUSED
    assert running.paused_by_lock is True
    assert running.gpu == "GPU 1"
    assert running.detail == "Paused by gaming lock"
    assert executor.interrupted == ["texture-upscaler"]

    lock.release()
    assert queue.apply_lock() == []
    assert running.state is JobState.PAUSED
    assert executor.started == []

    resumed = queue.resume()
    assert resumed.state is JobState.RUNNING
    assert resumed.paused_by_lock is False
    assert resumed.gpu == "GPU 1"
    assert resumed.detail == "Running on GPU 1"
    assert executor.started == ["texture-upscaler"]


def test_interrupt_failure_still_pauses_locally(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    executor.fail_interrupt = True
    lock = GamingLock(tmp_path / "gaming.lock")
    running = _job("pixeldreamer", JobState.RUNNING, gpu="GPU 0")
    queue = JobQueue([running], lock, executor)
    lock.engage()

    queue.apply_lock()
    assert running.state is JobState.PAUSED
    assert "interrupt failed" in running.detail
    assert executor.interrupted == ["pixeldreamer"]


def test_adding_a_job_does_not_start_it_while_locked(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    lock = GamingLock(tmp_path / "gaming.lock", environ={"LORA_QUEUE_GAMING_LOCK": "on"})
    queue = JobQueue([], lock, executor)
    job = _job("portrait", JobState.WAITING)
    queue.add(job)

    with pytest.raises(LockEngagedError):
        queue.start()
    assert job.state is JobState.WAITING
    assert executor.started == []


def test_start_picks_the_first_waiting_job(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    lock = GamingLock(tmp_path / "gaming.lock")
    first = _job("first", JobState.WAITING)
    second = _job("second", JobState.WAITING)
    queue = JobQueue([first, second], lock, executor)

    started = queue.start()
    assert started is first
    assert first.state is JobState.RUNNING
    assert first.gpu == "GPU 0"
    assert second.state is JobState.WAITING
    assert executor.started == ["first"]


def test_start_refuses_a_paused_job(tmp_path: Path) -> None:
    queue = JobQueue(
        [_job("held", JobState.PAUSED)],
        GamingLock(tmp_path / "gaming.lock"),
        RecordingExecutor(),
    )
    with pytest.raises(ValueError, match="Use resume"):
        queue.start("held")


def test_manual_pause(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    running = _job("pixeldreamer", JobState.RUNNING, gpu="GPU 0")
    queue = JobQueue([running], GamingLock(tmp_path / "gaming.lock"), executor)
    queue.pause()
    assert running.state is JobState.PAUSED
    assert running.paused_by_lock is False
    assert running.detail == "Paused"
    assert executor.interrupted == ["pixeldreamer"]


def test_resume_prefers_a_lock_held_job(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    manual = _job("manual", JobState.PAUSED, paused_by_lock=False)
    held = _job("held", JobState.PAUSED, paused_by_lock=True, gpu="GPU 1")
    queue = JobQueue([manual, held], GamingLock(tmp_path / "gaming.lock"), executor)
    resumed = queue.resume()
    assert resumed is held
    assert manual.state is JobState.PAUSED
