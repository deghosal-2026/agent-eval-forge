import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from evalforge.adapters.http import HttpAdapter
from evalforge.models.pack import Scenario


def make_scenario() -> Scenario:
    return Scenario(id="sc-1", title="T", input="hello")


class Handler(BaseHTTPRequestHandler):
    """Echo server: dispatch on the invocation payload's `input` field.

    - ``input="raw"`` → plain-text 200 (exercises the raw-text fallback).
    - ``input="fail500"`` → HTTP 500 (exercises the error path).
    - anything else → a `evalforge.run_envelope.v1` envelope.
    """

    def do_POST(self) -> None:  # http.server API uses this name
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        scenario_input = payload.get("input")
        if scenario_input == "raw":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"raw http answer")
            return
        if scenario_input == "fail500":
            self.send_response(500)
            self.end_headers()
            return
        envelope = {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "completed",
            "output": {"final": "http ok", "structured": None},
            "trajectory": {"steps": []},
            "cost": None,
            "error": None,
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(envelope).encode())

    def log_message(self, format: str, *args: object) -> None:  # silence server logs
        pass


@pytest.fixture(scope="module")
def server_url() -> str:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_http_envelope(server_url: str) -> None:
    adapter = HttpAdapter()
    artifact = adapter.run(
        make_scenario(),
        {"url": server_url, "run_id": "run-1", "timeout_seconds": 5},
    )
    assert artifact.status == "completed"
    assert artifact.output.final == "http ok"


def test_http_non_200_marks_error(server_url: str) -> None:
    adapter = HttpAdapter()
    config = {"url": server_url, "run_id": "run-1", "timeout_seconds": 5}
    artifact = adapter.run(Scenario(id="sc-2", title="T", input="fail500"), config)
    assert artifact.status == "error"


def test_http_connection_error() -> None:
    adapter = HttpAdapter()
    artifact = adapter.run(
        make_scenario(),
        {"url": "http://127.0.0.1:1/run", "run_id": "run-1", "timeout_seconds": 2},
    )
    assert artifact.status == "error"


def test_http_raw_text_fallback(server_url: str) -> None:
    adapter = HttpAdapter()
    artifact = adapter.run(
        Scenario(id="sc-3", title="T", input="raw"),
        {"url": server_url, "run_id": "run-1", "timeout_seconds": 5},
    )
    assert artifact.status == "completed"
    assert artifact.output.final == "raw http answer"
