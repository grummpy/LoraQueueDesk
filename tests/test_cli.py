import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from lora_queue_desk.cli import main
from lora_queue_desk.models import Job, JobState
from lora_queue_desk.store import JsonJobStore

ROOT = Path(__file__).resolve().parents[1]


def _demo(tmp_path: Path, *args: str) -> list[str]:
    return ["--demo", "--data-dir", str(tmp_path), *args]


def test_help_lists_the_main_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    assert "status" in text
    assert "lock" in text
    assert "queue" in text


def test_demo_status_has_every_state_and_no_network(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("network")

    monkeypatch.setattr("lora_queue_desk.comfy.http.urllib.request.urlopen", boom)
    assert main(_demo(tmp_path, "status")) == 0
    out = capsys.readouterr().out
    assert "http://192.168.4.47:8188" in out
    assert "(demo)" in out
    assert "PixelDreamer v2" in out
    assert "RPG Avatars" in out
    assert "Texture Upscaler" in out
    assert "Icon Sheet" in out
    for state in ("running", "paused", "waiting"):
        assert state in out
    assert "installed" in out
    assert "icon-sheet" in out
    assert (tmp_path / "demo-queue.json").is_file()
    assert not (tmp_path / "queue.json").exists()


def test_lock_blocks_resume_until_it_is_cleared(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(_demo(tmp_path, "lock", "on")) == 0
    turned_on = capsys.readouterr().out
    assert "Lock     on" in turned_on
    assert "PixelDreamer v2" in turned_on
    assert "Texture Upscaler" in turned_on

    assert main(_demo(tmp_path, "resume", "rpg-avatars")) == 3
    assert "Refusing to resume" in capsys.readouterr().err

    assert main(_demo(tmp_path, "start", "icon-sheet")) == 3
    assert "Refusing to start" in capsys.readouterr().err

    jobs = JsonJobStore(tmp_path / "demo-queue.json").load()
    by_id = {job.id: job for job in jobs}
    assert by_id["icon-sheet"].state is JobState.WAITING
    assert by_id["rpg-avatars"].state is JobState.PAUSED
    assert by_id["pixeldreamer"].state is JobState.PAUSED

    assert main(_demo(tmp_path, "lock", "off")) == 0
    released = capsys.readouterr().out
    assert "Lock     off" in released
    assert "lora-queue resume" in released

    assert main(_demo(tmp_path, "resume", "rpg-avatars")) == 0
    assert "Running  rpg-avatars" in capsys.readouterr().out
    reloaded = {job.id: job for job in JsonJobStore(tmp_path / "demo-queue.json").load()}
    assert reloaded["rpg-avatars"].state is JobState.RUNNING
    assert reloaded["pixeldreamer"].state is JobState.PAUSED


def test_queue_add_and_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            _demo(
                tmp_path,
                "queue",
                "add",
                "--name",
                "Portrait Styles",
                "--lora",
                "portrait-styles",
                "--rank",
                "4",
                "--precision",
                "fp8",
            )
        )
        == 0
    )
    assert "Waiting  portrait-styles" in capsys.readouterr().out
    assert main(_demo(tmp_path, "queue")) == 0
    listed = capsys.readouterr().out
    assert "portrait-styles" in listed
    assert "waiting" in listed
    assert main(_demo(tmp_path, "queue", "add", "--name", "Bad", "--lora", "bad", "--rank", "0")) == 4


def test_env_lock_survives_lock_off(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LORA_QUEUE_GAMING_LOCK", "on")
    assert main(_demo(tmp_path, "lock", "off")) == 0
    out = capsys.readouterr().out
    assert "Lock     on" in out
    assert "env" in out
    assert "Still on" in out
    assert main(_demo(tmp_path, "start")) == 3


def test_status_when_comfy_is_down(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    JsonJobStore(tmp_path / "queue.json").save(
        [
            Job(
                id="pixeldreamer",
                name="PixelDreamer v2",
                state=JobState.WAITING,
                lora="pixel-dreamer-v2",
            )
        ]
    )

    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("lora_queue_desk.comfy.http.urllib.request.urlopen", boom)
    assert main(["--data-dir", str(tmp_path), "--comfy-url", "http://192.168.4.47:8188", "status"]) == 0
    out = capsys.readouterr().out
    assert "PixelDreamer v2" in out
    assert "unreachable" in out
    assert main(["--data-dir", str(tmp_path), "start", "pixeldreamer"]) == 5
    reloaded = JsonJobStore(tmp_path / "queue.json").load()
    assert reloaded[0].state is JobState.WAITING


def test_refuses_remote_bind(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(_demo(tmp_path, "serve", "--host", "0.0.0.0", "--port", "9"))
    assert code == 4
    assert "non-loopback" in capsys.readouterr().err


def test_module_entrypoint(tmp_path: Path) -> None:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("LORA_QUEUE_") or key == "XDG_DATA_HOME":
            env.pop(key, None)
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "lora_queue_desk", "--demo", "--data-dir", str(tmp_path), "queue"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "pixeldreamer" in completed.stdout
    assert "icon-sheet" in completed.stdout
