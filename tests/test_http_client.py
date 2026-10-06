import json
import urllib.error
import urllib.request

import pytest

from lora_queue_desk.comfy.errors import ComfyError, ComfyHTTPError, ComfyUnavailable
from lora_queue_desk.comfy.http import HttpComfyClient, UrllibTransport
from lora_queue_desk.config import DEFAULT_COMFY_URL
from tests.fakes import FakeTransport


def _routes() -> dict[tuple[str, str], tuple[int, object]]:
    return {
        ("GET", "/system_stats"): (200, {"system": {"os": "linux"}, "devices": [{"name": "cuda:0"}]}),
        ("GET", "/models/loras"): (200, ["pixel-dreamer-v2.safetensors"]),
        ("GET", "/queue"): (200, {"queue_running": [[1]], "queue_pending": []}),
        ("POST", "/interrupt"): (200, None),
        ("POST", "/prompt"): (200, {"prompt_id": "abc"}),
        ("GET", "/api/system_stats"): (200, {"devices": []}),
    }


def test_reads_and_submit_stub() -> None:
    transport = FakeTransport(_routes())
    client = HttpComfyClient(DEFAULT_COMFY_URL + "/", transport=transport)

    health = client.health()
    assert health["devices"][0]["name"] == "cuda:0"
    assert client.list_lora_files() == ["pixel-dreamer-v2.safetensors"]
    assert client.prompt_queue()["queue_running"] == [[1]]
    client.interrupt()
    prompt_id = client.submit_prompt({"3": {"class_type": "Note"}}, client_id="desk")

    assert prompt_id == "abc"
    assert [call.path for call in transport.calls] == [
        "/system_stats",
        "/models/loras",
        "/queue",
        "/interrupt",
        "/prompt",
    ]
    assert transport.calls[0].url == "http://192.168.4.47:8188/system_stats"
    posted = json.loads(transport.calls[-1].body or b"{}")
    assert posted["client_id"] == "desk"
    assert posted["prompt"]["3"]["class_type"] == "Note"


def test_api_prefix_and_http_error() -> None:
    transport = FakeTransport({("GET", "/api/models/loras"): (404, b"missing")})
    client = HttpComfyClient("http://192.168.4.47:8188", api_prefix="api", transport=transport)
    with pytest.raises(ComfyHTTPError) as exc:
        client.list_lora_files()
    assert exc.value.status == 404
    assert transport.calls[0].url == "http://192.168.4.47:8188/api/models/loras"


def test_non_json_body() -> None:
    transport = FakeTransport({("GET", "/system_stats"): (200, b"nope")})
    client = HttpComfyClient(DEFAULT_COMFY_URL, transport=transport)
    with pytest.raises(ComfyError, match="non-JSON"):
        client.health()


def test_urllib_transport_does_not_use_a_real_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class Response:
        status = 200

        def read(self) -> bytes:
            return b'{"devices": []}'

        def __enter__(self) -> object:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None) -> Response:
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = HttpComfyClient(DEFAULT_COMFY_URL, timeout=2.5)
    assert isinstance(client.transport, UrllibTransport)
    assert client.health() == {"devices": []}
    assert seen == {
        "url": "http://192.168.4.47:8188/system_stats",
        "method": "GET",
        "timeout": 2.5,
    }


def test_urllib_transport_maps_url_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None) -> object:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = HttpComfyClient(DEFAULT_COMFY_URL)
    with pytest.raises(ComfyUnavailable, match="Cannot reach"):
        client.health()


def test_urllib_transport_maps_direct_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def read(self) -> bytes:
            raise TimeoutError("read timed out")

        def __enter__(self) -> object:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: Response())
    client = HttpComfyClient(DEFAULT_COMFY_URL)
    with pytest.raises(ComfyUnavailable, match="timed out"):
        client.health()


def test_urllib_transport_maps_http_error_body_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class TimedOutBody:
        def read(self) -> bytes:
            raise TimeoutError("error body timed out")

        def close(self) -> None:
            pass

    error = urllib.error.HTTPError(
        "http://example.invalid/system_stats",
        503,
        "Service Unavailable",
        None,
        TimedOutBody(),
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    client = HttpComfyClient(DEFAULT_COMFY_URL)
    with pytest.raises(ComfyUnavailable, match="error response"):
        client.health()
