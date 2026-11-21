"""What the queue is allowed to do to a backend.

``start`` checks that the backend answers. It does not submit a prompt.
``start`` deliberately does not submit a prompt, so local plan rows have no
backend prompt identity.  A backend-wide interrupt would therefore be unsafe:
it could stop work the desk did not start.  Local plans can still be paused.
"""

from __future__ import annotations

from typing import Protocol

from lora_queue_desk.comfy.protocol import ComfyClient
from lora_queue_desk.models import Job


class BackendOwnershipUnavailable(RuntimeError):
    """A local plan cannot be safely matched to a backend prompt."""


class Executor(Protocol):
    def start(self, job: Job) -> None: ...

    def interrupt(self, job: Job) -> None: ...


class ClientExecutor:
    def __init__(self, client: ComfyClient) -> None:
        self.client = client

    def start(self, job: Job) -> None:
        self.client.health()

    def interrupt(self, job: Job) -> None:
        raise BackendOwnershipUnavailable(
            "the desk did not submit a backend prompt for this local plan"
        )
