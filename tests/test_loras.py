from lora_queue_desk.loras import classify_loras, stem_name
from lora_queue_desk.models import Job, JobState


def _job(lora: str) -> Job:
    return Job(id=lora, name=lora, state=JobState.WAITING, lora=lora)


def test_stem_strips_weight_suffixes() -> None:
    assert stem_name("models/loras/pixel-dreamer-v2.safetensors") == "pixel-dreamer-v2"
    assert stem_name("pack.ckpt") == "pack"
    assert stem_name("notes.txt") == "notes.txt"


def test_installed_versus_waiting() -> None:
    files = [
        "pixel-dreamer-v2.safetensors",
        "rpg-avatars.safetensors",
        "texture-upscaler.safetensors",
        "unused-style.safetensors",
    ]
    jobs = [_job("pixel-dreamer-v2"), _job("icon-sheet"), _job("pixel-dreamer-v2")]
    installed, waiting = classify_loras(files, jobs)
    assert [pack.name for pack in installed] == [
        "pixel-dreamer-v2",
        "rpg-avatars",
        "texture-upscaler",
        "unused-style",
    ]
    assert [pack.name for pack in waiting] == ["icon-sheet"]
    assert installed[0].filename == "pixel-dreamer-v2.safetensors"
    assert waiting[0].installed is False
