"""ComfyUI clients.

``HttpComfyClient`` speaks the real HTTP API.
``MockComfyClient`` is the demo stand-in and never opens a socket.
"""

from lora_queue_desk.comfy.errors import ComfyError, ComfyHTTPError, ComfyUnavailable
from lora_queue_desk.comfy.http import HttpComfyClient
from lora_queue_desk.comfy.mock import MockComfyClient
from lora_queue_desk.comfy.protocol import ComfyClient

__all__ = [
    "ComfyClient",
    "ComfyError",
    "ComfyHTTPError",
    "ComfyUnavailable",
    "HttpComfyClient",
    "MockComfyClient",
]
