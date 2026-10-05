import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("LORA_QUEUE_") or key == "XDG_DATA_HOME":
            monkeypatch.delenv(key, raising=False)
