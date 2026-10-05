import threading
import urllib.error
import urllib.request
from pathlib import Path

from lora_queue_desk.config import Config
from lora_queue_desk.demo import demo_jobs
from lora_queue_desk.lock import GamingLock
from lora_queue_desk.store import JsonJobStore
from lora_queue_desk.web import loopback_host, make_server


def test_loopback_helper() -> None:
    assert loopback_host("127.0.0.1") is True
    assert loopback_host("localhost") is True
    assert loopback_host("0.0.0.0") is False


def test_status_page_on_loopback(tmp_path: Path) -> None:
    config = Config.load(demo=True, data_dir=str(tmp_path))
    server = make_server(config, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=3) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200
        assert "PixelDreamer v2" in body
        assert "Icon Sheet" in body
        assert "lock off" in body
        with urllib.request.urlopen(f"http://{host}:{port}/favicon.ico", timeout=3) as icon:
            assert icon.status == 204
        try:
            urllib.request.urlopen(f"http://{host}:{port}/nope", timeout=3)
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("expected a 404")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_status_get_does_not_apply_the_gaming_lock(tmp_path: Path) -> None:
    config = Config.load(demo=True, data_dir=str(tmp_path))
    JsonJobStore(tmp_path / "demo-queue.json").save(demo_jobs())
    GamingLock(tmp_path / "gaming.lock").engage()
    server = make_server(config, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=3) as response:
            assert response.status == 200
        jobs = JsonJobStore(tmp_path / "demo-queue.json").load()
        assert any(job.state.value == "running" for job in jobs)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
