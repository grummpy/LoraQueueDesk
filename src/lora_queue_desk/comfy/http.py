"""HTTP client for ComfyUI.

Reads ``/system_stats``, ``/models/loras``, and ``/queue``.
``interrupt`` posts ``/interrupt`` so a pause can ask the server to stop.
``submit_prompt`` posts a workflow you already built to ``/prompt``.

This starter does not build a training graph and the desk does not call
``submit_prompt`` when a job is marked running. Pointing the URL at a live
server therefore cannot start a GPU job by itself.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping, Protocol

from lora_queue_desk.comfy.errors import ComfyError, ComfyHTTPError, ComfyUnavailable


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> tuple[int, bytes]:
        """Return HTTP status and raw body. Raise ComfyUnavailable if the host is unreachable."""


class UrllibTransport:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read()
                status = int(getattr(response, "status", 200))
                return status, payload
        except urllib.error.HTTPError as exc:
            try:
                payload = exc.read()
            except TimeoutError as timeout:
                # HTTPError carries its response body separately. A stalled
                # error body is still an unavailable backend, not a raw
                # exception that can hide the local queue/status page.
                raise ComfyUnavailable(f"ComfyUI timed out while reading an error response at {url}") from timeout
            return int(exc.code), payload
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise ComfyUnavailable(f"Cannot reach ComfyUI at {url}: {reason}") from exc
        except TimeoutError as exc:
            # urlopen can surface timeouts directly while opening a connection
            # or while reading a response body.  Normalize both paths so the
            # desk can retain and display its local queue.
            raise ComfyUnavailable(f"ComfyUI timed out at {url}") from exc


class HttpComfyClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 3.0,
        api_prefix: str = "",
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        prefix = api_prefix.strip().rstrip("/")
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        self.api_prefix = prefix
        self.transport = transport if transport is not None else UrllibTransport(timeout)

    def health(self) -> dict[str, Any]:
        data = self._request("GET", "/system_stats")
        if not isinstance(data, dict):
            raise ComfyError("ComfyUI /system_stats did not return an object")
        return data

    def list_lora_files(self) -> list[str]:
        data = self._request("GET", "/models/loras")
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ComfyError("ComfyUI /models/loras did not return a list of filenames")
        return list(data)

    def prompt_queue(self) -> dict[str, Any]:
        data = self._request("GET", "/queue")
        if not isinstance(data, dict):
            raise ComfyError("ComfyUI /queue did not return an object")
        return data

    def interrupt(self) -> None:
        self._request("POST", "/interrupt", {})

    def submit_prompt(self, prompt: Mapping[str, Any], client_id: str | None = None) -> str:
        payload: dict[str, Any] = {"prompt": dict(prompt)}
        if client_id:
            payload["client_id"] = client_id
        data = self._request("POST", "/prompt", payload)
        if not isinstance(data, dict) or "prompt_id" not in data:
            raise ComfyError("ComfyUI /prompt response had no prompt_id")
        return str(data["prompt_id"])

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{self.api_prefix}{path}"

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(dict(payload)).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = self._url(path)
        status, raw = self.transport.request(method, url, body, headers)
        if status >= 400:
            text = raw.decode("utf-8", errors="replace")[:500]
            raise ComfyHTTPError(status, url, text)
        if not raw.strip():
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ComfyError(f"ComfyUI returned non-JSON from {path}") from exc
