import json
from pathlib import Path

import pytest

from lora_queue_desk.demo import demo_jobs
from lora_queue_desk.models import JobState
from lora_queue_desk.store import JsonJobStore, StoreError


def test_round_trip(tmp_path: Path) -> None:
    store = JsonJobStore(tmp_path / "queue.json")
    assert store.load() == []
    store.save(demo_jobs())
    loaded = store.load()
    assert [job.id for job in loaded] == [job.id for job in demo_jobs()]
    assert loaded[0].state is JobState.RUNNING
    assert loaded[1].paused_by_lock is True
    assert not (tmp_path / "queue.json.tmp").exists()


def test_invalid_json_and_state(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    store = JsonJobStore(path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(StoreError, match="not valid JSON"):
        store.load()

    path.write_text(json.dumps({"jobs": [{"id": "x", "name": "X", "state": "cooking", "lora": "x"}]}), encoding="utf-8")
    with pytest.raises(StoreError, match="invalid job"):
        store.load()
