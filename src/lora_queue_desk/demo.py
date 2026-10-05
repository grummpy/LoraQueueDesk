"""Fixture desk used by ``--demo``. No network."""

from __future__ import annotations

from lora_queue_desk.models import Job, JobState

DEMO_LORA_FILES = [
    "pixel-dreamer-v2.safetensors",
    "rpg-avatars.safetensors",
    "texture-upscaler.safetensors",
]


def demo_jobs() -> list[Job]:
    """Cover jobs, plus one waiting job so all three states are visible.

    RPG Avatars stays paused with ``paused_by_lock`` even though the demo
    starts with the lock off. Releasing the lock must not resume GPU work.
    """

    return [
        Job(
            id="pixeldreamer",
            name="PixelDreamer v2",
            state=JobState.RUNNING,
            lora="pixel-dreamer-v2",
            rank=32,
            precision="BF16",
            progress=65,
            gpu="GPU 0",
            detail="Running on GPU 0",
        ),
        Job(
            id="rpg-avatars",
            name="RPG Avatars",
            state=JobState.PAUSED,
            lora="rpg-avatars",
            rank=16,
            precision="BF16",
            progress=0,
            gpu="GPU 0",
            paused_by_lock=True,
            detail="Paused by gaming lock",
        ),
        Job(
            id="texture-upscaler",
            name="Texture Upscaler",
            state=JobState.RUNNING,
            lora="texture-upscaler",
            rank=64,
            precision="FP8",
            progress=28,
            gpu="GPU 1",
            detail="Running on GPU 1",
        ),
        Job(
            id="icon-sheet",
            name="Icon Sheet",
            state=JobState.WAITING,
            lora="icon-sheet",
            rank=8,
            precision="BF16",
            progress=0,
            detail="Waiting for a free GPU",
        ),
    ]
