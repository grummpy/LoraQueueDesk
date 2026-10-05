from pathlib import Path

import pytest

from lora_queue_desk.comfy.errors import ComfyUnavailable
from lora_queue_desk.comfy.http import HttpComfyClient
from lora_queue_desk.comfy.mock import MockComfyClient
from lora_queue_desk.config import DEFAULT_COMFY_URL, Config
from lora_queue_desk.demo import demo_jobs
from lora_queue_desk.desk import Desk
from lora_queue_desk.executor import ClientExecutor
from lora_queue_desk.lock import GamingLock, LockEngagedError
from lora_queue_desk.models import Job, JobState
from lora_queue_desk.queue import JobQueue
from lora_queue_desk.render import render_status
from lora_queue_desk.store import JsonJobStore
from tests.fakes import FakeTransport


def _http_desk(tmp_path: Path, jobs: list[Job]) -> tuple[Desk, FakeTransport]:
    transport = FakeTransport(
        {
            ("GET", "/system_stats"): (200, {"devices": [{"name": "cuda:0"}]}),
            ("GET", "/models/loras"): (200, ["pixel-dreamer-v2.safetensors"]),
            ("GET", "/queue"): (200, {"queue_running": [], "queue_pending": []}),
            ("POST", "/interrupt"): (200, {}),
            ("POST", "/prompt"): (200, {"prompt_id": "should-not-be-called"}),
        }
    )
    config = Config(comfy_url=DEFAULT_COMFY_URL, demo=False, data_dir=tmp_path)
    client = HttpComfyClient(config.comfy_url, transport=transport)
    store = JsonJobStore(tmp_path / "queue.json")
    lock = GamingLock(tmp_path / "gaming.lock")
    queue = JobQueue(jobs, lock, ClientExecutor(client))
    return Desk(config, client, lock, store, queue), transport


def test_http_start_checks_health_and_does_not_submit(tmp_path: Path) -> None:
    waiting = Job(id="icon-sheet", name="Icon Sheet", state=JobState.WAITING, lora="icon-sheet")
    desk, transport = _http_desk(tmp_path, [waiting])
    started = desk.start(None)
    assert started.state is JobState.RUNNING
    paths = [(call.method, call.path) for call in transport.calls]
    assert ("GET", "/system_stats") in paths
    assert ("POST", "/prompt") not in paths


def test_http_lock_interrupts_and_blocks_resume(tmp_path: Path) -> None:
    running = Job(
        id="pixeldreamer",
        name="PixelDreamer v2",
        state=JobState.RUNNING,
        lora="pixel-dreamer-v2",
        gpu="GPU 0",
        progress=65,
    )
    desk, transport = _http_desk(tmp_path, [running])
    _view, paused = desk.set_lock(True)
    assert [job.id for job in paused] == ["pixeldreamer"]
    assert running.state is JobState.PAUSED
    assert running.paused_by_lock is True
    with pytest.raises(LockEngagedError):
        desk.resume("pixeldreamer")
    assert running.state is JobState.PAUSED
    methods = [(call.method, call.path) for call in transport.calls]
    assert ("POST", "/interrupt") in methods
    assert ("POST", "/prompt") not in methods


def test_offline_mock_keeps_the_local_queue_visible(tmp_path: Path) -> None:
    config = Config(comfy_url=DEFAULT_COMFY_URL, demo=True, data_dir=tmp_path)
    client = MockComfyClient(online=False)
    store = JsonJobStore(tmp_path / "queue.json")
    jobs = demo_jobs()
    lock = GamingLock(tmp_path / "gaming.lock")
    desk = Desk(config, client, lock, store, JobQueue(jobs, lock, ClientExecutor(client)))
    text = render_status(desk.refresh())
    assert "PixelDreamer v2" in text
    assert "unreachable" in text
    assert "unavailable until ComfyUI answers" in text

    waiting = Job(id="extra", name="Extra", state=JobState.WAITING, lora="extra")
    desk.queue.jobs.append(waiting)
    with pytest.raises(ComfyUnavailable):
        desk.start("extra")
    assert waiting.state is JobState.WAITING
