from lora_queue_desk.models import DeskView, Job, JobState
from lora_queue_desk.render import render_html


def test_html_escapes_job_names() -> None:
    job = Job(
        id="x",
        name="<script>",
        state=JobState.WAITING,
        lora="pack&1",
        detail="a < b",
    )
    view = DeskView(
        comfy_url="http://192.168.4.47:8188",
        demo=True,
        lock_on=True,
        lock_sources=("file",),
        lock_path="/tmp/gaming.lock",
        jobs=(job,),
        installed=(),
        waiting=(),
        comfy_error=None,
        devices=(),
        prompt_running=0,
        prompt_pending=0,
    )
    page = render_html(view)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "pack&amp;1" in page
    assert "Gaming lock is on" in page
