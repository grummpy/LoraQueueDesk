"""Plain-text and single-page HTML views of a desk snapshot."""

from __future__ import annotations

import html

from lora_queue_desk import __version__
from lora_queue_desk.models import DeskView, Job, JobState


def render_status(view: DeskView) -> str:
    mode = "  (demo)" if view.demo else ""
    lines = [
        f"LoRA Queue Desk {__version__}",
        f"ComfyUI  {view.comfy_url}{mode}",
    ]
    if view.demo_source:
        lines.append(f"Mode     {'demo' if view.demo else 'live'} via {view.demo_source}")
    if view.comfy_error:
        lines.append(f"Reach    unreachable: {view.comfy_error}")
    elif view.devices:
        lines.append("Devices  " + ", ".join(view.devices))
    if view.prompt_running is not None and view.prompt_pending is not None:
        lines.append(
            f"Prompts  {view.prompt_running} running, {view.prompt_pending} pending"
        )
    lines.append("")
    lines.append(render_lock(view).rstrip("\n"))
    lines.append("")
    lines.append("Jobs")
    if not view.jobs:
        lines.append("  (none)")
    else:
        lines.extend(_job_line(job) for job in view.jobs)
    lines.append("")
    lines.append("LoRA packs")
    if view.comfy_error:
        lines.append("  unavailable until ComfyUI answers")
    elif not view.installed and not view.waiting:
        lines.append("  (none)")
    else:
        for pack in view.installed:
            filename = f"  {pack.filename}" if pack.filename else ""
            lines.append(f"  installed  {pack.name}{filename}")
        for pack in view.waiting:
            lines.append(f"  waiting    {pack.name}")
    return "\n".join(lines) + "\n"


def render_jobs(view: DeskView) -> str:
    lines = ["Jobs"]
    if not view.jobs:
        lines.append("  (none)")
    else:
        lines.extend(_job_line(job) for job in view.jobs)
    return "\n".join(lines) + "\n"


def render_loras(view: DeskView) -> str:
    lines = ["LoRA packs"]
    if view.comfy_error:
        lines.append("  unavailable until ComfyUI answers")
        lines.append(f"  {view.comfy_error}")
    elif not view.installed and not view.waiting:
        lines.append("  (none)")
    else:
        for pack in view.installed:
            filename = pack.filename or ""
            lines.append(f"  installed  {pack.name}  {filename}".rstrip())
        for pack in view.waiting:
            lines.append(f"  waiting    {pack.name}")
    return "\n".join(lines) + "\n"


def render_lock(view: DeskView) -> str:
    state = "on" if view.lock_on else "off"
    lines = [f"Lock     {state}"]
    if view.lock_sources:
        lines.append("Sources  " + ", ".join(view.lock_sources))
    lines.append(f"File     {view.lock_path}")
    lines.append("On       lora-queue lock on")
    lines.append("Off      lora-queue lock off")
    lines.append("Env      LORA_QUEUE_GAMING_LOCK or LORA_QUEUE_PRESENCE_LOCK = on")
    lines.append("Note     lock off does not resume jobs and does not unset the environment")
    return "\n".join(lines) + "\n"


def render_html(view: DeskView) -> str:
    rows = "\n".join(_job_row(job) for job in view.jobs) or (
        "<p class='empty'>No jobs in the local queue.</p>"
    )
    if view.comfy_error:
        packs = f"<p class='empty'>{_esc(view.comfy_error)}</p>"
    else:
        items = []
        for pack in view.installed:
            items.append(
                f"<li><span class='tag installed'>installed</span> {_esc(pack.name)}</li>"
            )
        for pack in view.waiting:
            items.append(f"<li><span class='tag waiting'>waiting</span> {_esc(pack.name)}</li>")
        packs = "<ul>" + "".join(items) + "</ul>" if items else "<p class='empty'>No packs.</p>"
    lock = "on" if view.lock_on else "off"
    sources = ", ".join(view.lock_sources) if view.lock_sources else "none"
    banner = ""
    if view.lock_on:
        banner = (
            "<p class='banner'>Gaming lock is on. Starts and resumes are blocked. "
            f"Sources: {_esc(sources)}.</p>"
        )
    reach = (
        f"<p class='warn'>{_esc(view.comfy_error)}</p>" if view.comfy_error else ""
    )
    mode = "demo" if view.demo else "live"
    mode_source = f" via {view.demo_source}" if view.demo_source else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LoRA Queue Desk</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; font: 16px/1.45 ui-sans-serif, system-ui, sans-serif;
    background: #10151c; color: #e7eef2; }}
  main {{ max-width: 880px; margin: 0 auto; padding: 32px 20px 64px; }}
  h1 {{ font-weight: 560; letter-spacing: -0.03em; margin: 0 0 8px; }}
  h1 span {{ color: #2ee6d6; }}
  .meta {{ color: #9aa8b2; margin: 0 0 20px; }}
  .banner {{ background: #3a2a12; color: #ffc56b; padding: 12px 14px; border-radius: 10px; }}
  .warn {{ color: #ffb4a8; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0 28px; }}
  th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #243040; }}
  th {{ color: #8ea0ad; font-weight: 600; font-size: 12px; letter-spacing: 0.06em; }}
  .running {{ color: #2ee6d6; }}
  .paused {{ color: #ffc56b; }}
  .waiting {{ color: #9aa8b2; }}
  .tag {{ display: inline-block; min-width: 5.5em; font-size: 12px; letter-spacing: 0.04em; }}
  .tag.installed {{ color: #2ee6d6; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ padding: 6px 0; }}
  .empty {{ color: #8ea0ad; }}
</style>
</head>
<body>
<main>
  <h1><span>LoRA</span> Queue Desk</h1>
  <p class="meta">{_esc(view.comfy_url)} · {_esc(mode + mode_source)} · lock {_esc(lock)}</p>
  {banner}
  {reach}
  <h2>Jobs</h2>
  <table>
    <thead><tr><th>STATE</th><th>JOB</th><th>PROGRESS</th><th>PACK</th></tr></thead>
    <tbody>
    {rows}
    </tbody>
  </table>
  <h2>LoRA packs</h2>
  {packs}
</main>
</body>
</html>
"""


def _job_line(job: Job) -> str:
    header = (
        f"  {job.state.value:<8} {job.id:<18} {job.name:<22} {_progress(job):>4}"
    )
    return f"{header}\n           {_spec(job)} · {job.detail}"


def _job_row(job: Job) -> str:
    return (
        "<tr>"
        f"<td class='{job.state.value}'>{_esc(job.state.value)}</td>"
        f"<td>{_esc(job.name)}</td>"
        f"<td>{_esc(_progress(job))}</td>"
        f"<td>{_esc(_spec(job))} · {_esc(job.detail)}</td>"
        "</tr>"
    )


def _spec(job: Job) -> str:
    bits = ["LoRA", job.lora]
    if job.rank is not None:
        bits.append(f"rank {job.rank}")
    if job.precision:
        bits.append(job.precision)
    return " · ".join(bits)


def _progress(job: Job) -> str:
    if job.state is JobState.RUNNING or job.progress:
        return f"{job.progress:.0f}%"
    return "—"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)
