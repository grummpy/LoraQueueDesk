"""Small read-only status page. Default bind is loopback only."""

from __future__ import annotations

import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lora_queue_desk.config import Config
from lora_queue_desk.desk import Desk
from lora_queue_desk.render import render_html


def loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def make_server(config: Config, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler name
            path = self.path.split("?", 1)[0]
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if path not in {"/", "/index.html"}:
                body = b"Not found\n"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            page = render_html(Desk.open(config).refresh()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def serve(config: Config, host: str, port: int) -> None:
    server = make_server(config, host, port)
    bound_host, bound_port = server.server_address[:2]
    print(f"LoRA Queue Desk listening on http://{bound_host}:{bound_port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()
