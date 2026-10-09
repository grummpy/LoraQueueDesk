"""Command line for the desk.

    lora-queue status
    lora-queue lock on|off
    lora-queue queue
"""

from __future__ import annotations

import argparse
import sys

from lora_queue_desk import __version__
from lora_queue_desk.comfy.errors import ComfyError
from lora_queue_desk.config import Config
from lora_queue_desk.desk import Desk
from lora_queue_desk.lock import LockEngagedError
from lora_queue_desk.models import JobState
from lora_queue_desk.render import render_jobs, render_lock, render_loras, render_status
from lora_queue_desk.store import StoreError
from lora_queue_desk.web import loopback_host, serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lora-queue",
        description="Local desk for a ComfyUI LoRA queue. The gaming lock blocks GPU starts.",
    )
    parser.add_argument("--version", action="version", version=f"lora-queue {__version__}")
    parser.add_argument("--demo", action="store_true", help="Use the mock ComfyUI client. No network.")
    parser.add_argument("--data-dir", help="Directory for queue.json and the gaming.lock flag.")
    parser.add_argument("--comfy-url", help="ComfyUI base URL. Default http://192.168.4.47:8188.")
    parser.add_argument("--config", help="TOML config file. Default ./lora-queue.toml when present.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show the lock, jobs, and installed versus waiting packs.")
    sub.add_parser("demo", help="Show status with the mock client and the sample queue.")
    sub.add_parser("loras", help="List installed packs and packs still waiting.")

    lock = sub.add_parser("lock", help="Show or flip the gaming / presence lock.")
    lock_sub = lock.add_subparsers(dest="lock_action")
    lock_sub.add_parser("on", help="Write the flag file and pause running jobs.")
    lock_sub.add_parser("off", help="Delete the flag file. Does not resume jobs.")
    lock_sub.add_parser("status", help="Show whether the lock is on and why.")

    queue = sub.add_parser("queue", help="List the local queue. Use 'queue add' to enqueue.")
    queue_sub = queue.add_subparsers(dest="queue_action")
    add = queue_sub.add_parser("add", help="Append a waiting job. Does not start it.")
    add.add_argument("--name", required=True)
    add.add_argument("--lora", required=True, help="Pack stem, matching the ComfyUI filename without the extension.")
    add.add_argument("--rank", type=int)
    add.add_argument("--precision", default="BF16")

    start = sub.add_parser("start", help="Start a waiting job, or the first waiting job.")
    start.add_argument("job_id", nargs="?")
    pause = sub.add_parser("pause", help="Pause a running job, or every running job.")
    pause.add_argument("job_id", nargs="?")
    resume = sub.add_parser("resume", help="Resume a paused job once the lock is off.")
    resume.add_argument("job_id", nargs="?")

    web = sub.add_parser("serve", help="Serve a read-only status page on loopback.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow a non-loopback host. Off by default.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except LockEngagedError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (StoreError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except ComfyError as exc:
        print(str(exc), file=sys.stderr)
        return 5


def _run(args: argparse.Namespace) -> int:
    config = Config.load(
        demo=bool(args.demo or args.command == "demo"),
        data_dir=args.data_dir,
        comfy_url=args.comfy_url,
        config_path=args.config,
    )
    if args.command == "serve":
        if not loopback_host(args.host) and not args.allow_remote:
            print(
                "Refusing to bind a non-loopback host without --allow-remote.",
                file=sys.stderr,
            )
            return 4
        serve(config, args.host, args.port)
        return 0

    desk = Desk.open(config)
    if args.command in {"status", "demo"}:
        print(render_status(desk.refresh()), end="")
        return 0
    if args.command == "loras":
        print(render_loras(desk.refresh()), end="")
        return 0
    if args.command == "lock":
        return _lock(desk, args.lock_action)
    if args.command == "queue":
        return _queue(desk, args)
    if args.command == "start":
        job = desk.start(args.job_id)
        print(f"Running  {job.id}  {job.name}  {job.detail}")
        return 0
    if args.command == "pause":
        paused = desk.pause(args.job_id)
        for job in paused:
            print(f"Paused   {job.id}  {job.name}")
        return 0
    if args.command == "resume":
        job = desk.resume(args.job_id)
        print(f"Running  {job.id}  {job.name}  {job.detail}")
        return 0
    raise ValueError(f"Unknown command {args.command}")


def _lock(desk: Desk, action: str | None) -> int:
    if action in {None, "status"}:
        print(render_lock(desk.refresh()), end="")
        return 0
    if action == "on":
        view, paused = desk.set_lock(True)
        print(render_lock(view), end="")
        if paused:
            names = ", ".join(job.name for job in paused)
            print(f"Paused   {names}")
        else:
            still_running = [job.name for job in view.jobs if job.state is JobState.RUNNING]
            if still_running:
                print(f"Still running   {', '.join(still_running)} (backend interrupt failed)")
            else:
                print("Paused   (no running jobs)")
        return 0
    if action == "off":
        view, _paused = desk.set_lock(False)
        print(render_lock(view), end="")
        if view.lock_on:
            print("Still on. The flag file is gone, but another source is engaged.")
        else:
            print("Jobs stay paused until you run: lora-queue resume")
        return 0
    raise ValueError(f"Unknown lock action {action}")


def _queue(desk: Desk, args: argparse.Namespace) -> int:
    if args.queue_action is None:
        print(render_jobs(desk.refresh()), end="")
        return 0
    if args.queue_action == "add":
        job = desk.add_job(
            name=args.name,
            lora=args.lora,
            rank=args.rank,
            precision=args.precision,
        )
        print(f"Waiting  {job.id}  {job.name}  LoRA {job.lora}")
        return 0
    raise ValueError(f"Unknown queue action {args.queue_action}")
