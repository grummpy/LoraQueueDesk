"""Errors from a ComfyUI client. These are not gaming-lock refusals."""


class ComfyError(RuntimeError):
    """The ComfyUI client got a response it cannot use."""


class ComfyUnavailable(ComfyError):
    """The server could not be reached. No request completed."""


class ComfyHTTPError(ComfyError):
    def __init__(self, status: int, url: str, body: str) -> None:
        self.status = status
        self.url = url
        self.body = body
        super().__init__(f"ComfyUI {status} from {url}: {body}")
