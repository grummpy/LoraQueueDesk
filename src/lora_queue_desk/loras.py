"""Split LoRA packs into installed (on the ComfyUI model list) and waiting."""

from __future__ import annotations

from lora_queue_desk.models import Job, LoraPack

_WEIGHT_SUFFIXES = (".safetensors", ".ckpt", ".pt", ".bin")


def stem_name(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    lower = name.lower()
    for suffix in _WEIGHT_SUFFIXES:
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return name


def classify_loras(filenames: list[str], jobs: list[Job]) -> tuple[list[LoraPack], list[LoraPack]]:
    """Jobs name a pack by its filename stem.

    A referenced stem that is absent from ``filenames`` is waiting.
    Installed files that no job mentions are still listed as installed.
    """

    by_stem: dict[str, str] = {}
    for filename in filenames:
        by_stem.setdefault(stem_name(filename), filename)

    installed: list[LoraPack] = []
    waiting: list[LoraPack] = []
    seen: set[str] = set()
    for job in jobs:
        if job.lora in seen:
            continue
        seen.add(job.lora)
        filename = by_stem.get(job.lora)
        if filename is None:
            waiting.append(LoraPack(name=job.lora, installed=False, filename=None))
        else:
            installed.append(LoraPack(name=job.lora, installed=True, filename=filename))

    for stem, filename in by_stem.items():
        if stem in seen:
            continue
        installed.append(LoraPack(name=stem, installed=True, filename=filename))
    return installed, waiting
