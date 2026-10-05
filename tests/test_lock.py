from pathlib import Path

from lora_queue_desk.lock import GamingLock, NullPresenceDetector


def test_null_detector_is_clear() -> None:
    assert NullPresenceDetector().gaming_or_projection_active() is False


def test_missing_flag_is_off(tmp_path: Path) -> None:
    snapshot = GamingLock(tmp_path / "gaming.lock").snapshot()
    assert snapshot.engaged is False
    assert snapshot.sources == ()


def test_flag_file_on_and_off(tmp_path: Path) -> None:
    lock = GamingLock(tmp_path / "gaming.lock")
    lock.engage()
    assert lock.flag_path.read_text(encoding="utf-8") == "on\n"
    assert lock.snapshot().sources == ("file",)

    lock.release()
    assert not lock.flag_path.exists()
    assert lock.snapshot().engaged is False


def test_file_contents_off_do_not_engage(tmp_path: Path) -> None:
    path = tmp_path / "gaming.lock"
    path.write_text("off\n", encoding="utf-8")
    assert GamingLock(path).snapshot().engaged is False
    path.write_text("no\n", encoding="utf-8")
    assert GamingLock(path).snapshot().engaged is False


def test_empty_file_engages(tmp_path: Path) -> None:
    path = tmp_path / "gaming.lock"
    path.write_text("", encoding="utf-8")
    assert GamingLock(path).snapshot().engaged is True


def test_env_and_alias(tmp_path: Path) -> None:
    path = tmp_path / "gaming.lock"
    assert GamingLock(path, environ={"LORA_QUEUE_GAMING_LOCK": "on"}).snapshot().sources == ("env",)
    assert GamingLock(path, environ={"LORA_QUEUE_PRESENCE_LOCK": "yes"}).snapshot().engaged is True
    assert GamingLock(path, environ={"LORA_QUEUE_GAMING_LOCK": "0"}).snapshot().engaged is False
    both = {"LORA_QUEUE_GAMING_LOCK": "off", "LORA_QUEUE_PRESENCE_LOCK": "1"}
    assert GamingLock(path, environ=both).snapshot().engaged is True


def test_release_does_not_clear_environment(tmp_path: Path) -> None:
    path = tmp_path / "gaming.lock"
    lock = GamingLock(path, environ={"LORA_QUEUE_GAMING_LOCK": "true"})
    lock.engage()
    lock.release()
    snapshot = lock.snapshot()
    assert snapshot.engaged is True
    assert snapshot.sources == ("env",)


def test_detector_engages(tmp_path: Path) -> None:
    class Projector:
        def gaming_or_projection_active(self) -> bool:
            return True

    snapshot = GamingLock(tmp_path / "gaming.lock", detector=Projector()).snapshot()
    assert snapshot.sources == ("detector",)


def test_detector_error_fails_closed(tmp_path: Path) -> None:
    class Broken:
        def gaming_or_projection_active(self) -> bool:
            raise RuntimeError("no display")

    snapshot = GamingLock(tmp_path / "gaming.lock", detector=Broken()).snapshot()
    assert snapshot.engaged is True
    assert snapshot.sources == ("detector-error",)


def test_any_source_is_enough(tmp_path: Path) -> None:
    path = tmp_path / "gaming.lock"
    path.write_text("on\n", encoding="utf-8")

    class Clear:
        def gaming_or_projection_active(self) -> bool:
            return False

    snapshot = GamingLock(path, environ={}, detector=Clear()).snapshot()
    assert snapshot.sources == ("file",)
    assert snapshot.engaged is True
