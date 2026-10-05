from pathlib import Path

import pytest

from lora_queue_desk.config import DEFAULT_COMFY_URL, Config


def test_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    config = Config.load()
    assert config.comfy_url == DEFAULT_COMFY_URL == "http://192.168.4.47:8188"
    assert config.demo is False
    assert config.data_dir == tmp_path / "lora-queue-desk"
    assert config.timeout == 3.0
    assert config.api_prefix == ""


def test_cli_overrides_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "desk.toml"
    path.write_text(
        'comfy_url = "http://file.test:8188"\ndemo = true\napi_prefix = "api"\ntimeout = 9\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("LORA_QUEUE_COMFY_URL", "http://env.test:8188")
    from_env = Config.load(config_path=str(path))
    assert from_env.comfy_url == "http://env.test:8188"
    assert from_env.demo is True
    assert from_env.api_prefix == "/api"
    assert from_env.timeout == 9

    from_cli = Config.load(comfy_url="http://cli.test:8188", config_path=str(path))
    assert from_cli.comfy_url == "http://cli.test:8188"


def test_bad_url_and_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="http"):
        Config.load(comfy_url="192.168.4.47:8188")
    with pytest.raises(ValueError, match="not found"):
        Config.load(config_path=str(tmp_path / "missing.toml"))


def test_data_dir_flag(tmp_path: Path) -> None:
    config = Config.load(demo=True, data_dir=str(tmp_path / "state"))
    assert config.demo is True
    assert config.data_dir == tmp_path / "state"
