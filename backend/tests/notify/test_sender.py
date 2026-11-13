"""AppriseSender against a real local HTTP endpoint (json:// preset)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from finalarr.notify.sender import AppriseSender, SendError


@pytest.fixture
def endpoint():
    received = []
    state = {"status": 200}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(state["status"])
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"json://127.0.0.1:{server.server_port}/hook", received, state
    server.shutdown()


def test_sends_title_and_html_body(endpoint):
    url, received, _ = endpoint
    AppriseSender().send(url, "<b>Slime</b> komplett")
    assert received[0]["title"] == "Finalarr"
    assert "Slime" in received[0]["message"]


def test_http_error_becomes_a_send_error(endpoint):
    url, _, state = endpoint
    state["status"] = 500
    with pytest.raises(SendError):
        AppriseSender().send(url, "x")


def test_unusable_url_is_a_send_error():
    with pytest.raises(SendError, match="not accepted"):
        AppriseSender().send("nonsense://x", "x")
