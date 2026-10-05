from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class Call:
    method: str
    url: str
    path: str
    body: bytes | None


class FakeTransport:
    def __init__(self, routes: dict[tuple[str, str], tuple[int, object]]) -> None:
        self.routes = routes
        self.calls: list[Call] = []

    def request(self, method: str, url: str, body: bytes | None, headers: object) -> tuple[int, bytes]:
        path = urlparse(url).path
        self.calls.append(Call(method, url, path, body))
        status, payload = self.routes[(method, path)]
        if payload is None:
            raw = b""
        elif isinstance(payload, (dict, list)):
            raw = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, bytes):
            raw = payload
        else:
            raise TypeError(f"unsupported payload {type(payload)}")
        return status, raw


class RecordingExecutor:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.interrupted: list[str] = []
        self.fail_interrupt = False

    def start(self, job: object) -> None:
        self.started.append(job.id)  # type: ignore[attr-defined]

    def interrupt(self, job: object) -> None:
        self.interrupted.append(job.id)  # type: ignore[attr-defined]
        if self.fail_interrupt:
            raise RuntimeError("gpu busy")
