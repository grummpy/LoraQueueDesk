"""What the queue is allowed to do to a backend.

``start`` checks that the backend answers. It does not submit a prompt.
``interrupt`` is the safe half of a pause: ask the backend to stop, then
the queue marks the job paused even if that call fails.
"""

from __future__ import annotations

from typing import Protocol

from lora_queue_desk.comfy.protocol import ComfyClient
from lora_queue_desk.models import Job


class Executor(Protocol):
    def start(self, job: Job) -> None: ...

    def interrupt(self, job: Job) -> None: ...


class ClientExecutor:
    def __init__(self, client: ComfyClient) -> None:
        self.client = client

    def start(self, job: Job) -> None:
        self.client.health()

    def interrupt(self, job: Job) -> None:
        self.client.interrupt()
