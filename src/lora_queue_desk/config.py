"""Configuration from CLI flags, the environment, and an optional TOML file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ always has tomllib
    tomllib = None  # type: ignore[assignment]

DEFAULT_COMFY_URL = "http://192.168.4.47:8188"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class Config:
    comfy_url: str
    demo: bool
    data_dir: Path
    timeout: float = 3.0
    api_prefix: str = ""

    @classmethod
    def load(
        cls,
        *,
        demo: bool = False,
        data_dir: str | None = None,
        comfy_url: str | None = None,
        config_path: str | None = None,
        environ: dict[str, str] | None = None,
    ) -> Config:
        env = os.environ if environ is None else environ
        file_data = _load_file(env, config_path)

        url = comfy_url or env.get("LORA_QUEUE_COMFY_URL") or _as_str(file_data.get("comfy_url"))
        url = (url or DEFAULT_COMFY_URL).strip().rstrip("/")
        _require_http_url(url)

        demo_env = (env.get("LORA_QUEUE_DEMO") or "").strip().lower()
        file_demo = bool(file_data.get("demo"))
        use_demo = bool(demo) or demo_env in _TRUTHY or file_demo

        directory = _data_dir(data_dir, env, file_data)
        timeout = _timeout(env, file_data)
        prefix = _api_prefix(env, file_data)
        return cls(
            comfy_url=url,
            demo=use_demo,
            data_dir=directory,
            timeout=timeout,
            api_prefix=prefix,
        )


def _load_file(env: dict[str, str] | os._Environ[str], config_path: str | None) -> dict:
    chosen = config_path or env.get("LORA_QUEUE_CONFIG")
    path = Path(chosen).expanduser() if chosen else Path("lora-queue.toml")
    if chosen is None and not path.exists():
        return {}
    if not path.is_file():
        raise ValueError(f"Config file not found: {path}")
    if tomllib is None:
        raise ValueError("TOML config needs Python 3.11 or newer")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a TOML table: {path}")
    return data


def _data_dir(explicit: str | None, env: dict[str, str] | os._Environ[str], file_data: dict) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if env.get("LORA_QUEUE_DATA_DIR"):
        return Path(env["LORA_QUEUE_DATA_DIR"]).expanduser()
    raw = file_data.get("data_dir")
    if isinstance(raw, str) and raw.strip():
        return Path(raw).expanduser()
    xdg = env.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "lora-queue-desk"


def _timeout(env: dict[str, str] | os._Environ[str], file_data: dict) -> float:
    raw = env.get("LORA_QUEUE_TIMEOUT")
    if raw is None or not str(raw).strip():
        raw = file_data.get("timeout", 3.0)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timeout must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ValueError("timeout must be greater than 0")
    return value


def _api_prefix(env: dict[str, str] | os._Environ[str], file_data: dict) -> str:
    raw = env.get("LORA_QUEUE_API_PREFIX")
    if raw is None:
        raw = file_data.get("api_prefix", "")
    prefix = str(raw or "").strip().rstrip("/")
    if prefix and not prefix.startswith("/"):
        prefix = "/" + prefix
    return prefix


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"ComfyUI URL must be http or https with a host, got {url!r}")
