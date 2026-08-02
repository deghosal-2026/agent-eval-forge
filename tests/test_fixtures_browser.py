from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evalforge.fixtures.browser import BrowserFixture, BrowserToolStub
from evalforge.fixtures.http_record import HTTPRecording
from evalforge.fixtures.tool_stub import FixtureNotFoundError

BROWSER_TEST_FIXTURE = Path(__file__).parent / "fixtures" / "http_browser_test.json"


def _load_test_fixture() -> dict[str, Any]:
    return json.loads(BROWSER_TEST_FIXTURE.read_text())


def test_browser_fixture_page_loading() -> None:
    data = _load_test_fixture()
    fixture = BrowserFixture(
        pages=data["pages"],
        cookies=data.get("cookies", {}),
        local_storage=data.get("local_storage", {}),
        responses=data.get("responses", {}),
    )

    login_html = fixture.get_page("https://example.com/login")
    assert "<title>Login</title>" in login_html

    dashboard_html = fixture.get_page("https://example.com/dashboard")
    assert "Welcome, Admin" in dashboard_html


def test_browser_fixture_get_page_content() -> None:
    data = _load_test_fixture()
    fixture = BrowserFixture(
        pages=data["pages"],
        responses=data.get("responses", {}),
    )

    content = fixture.get_page_content("https://example.com/dashboard")
    assert "Welcome, Admin" in content
    assert "3 unread messages" in content
    assert "<h1>" not in content


def test_browser_fixture_missing_page() -> None:
    fixture = BrowserFixture(pages={})

    with pytest.raises(FixtureNotFoundError, match="No page fixture for URL"):
        fixture.get_page("https://nonexistent.example.com")


def test_click_type_simulation() -> None:
    data = _load_test_fixture()
    fixture = BrowserFixture(
        pages=data["pages"],
        responses=data.get("responses", {}),
    )
    stub = BrowserToolStub(fixtures_dir=str(BROWSER_TEST_FIXTURE.parent))

    stub._browser_fixtures["default"] = fixture

    click_result = stub.click("#submit-btn", "https://example.com/login")
    assert click_result["action"] == "click"
    assert click_result["selector"] == "#submit-btn"
    assert "Login</title>" in click_result["html"]

    type_result = stub.type_text("input[name='username']", "admin")
    assert type_result["action"] == "type"
    assert type_result["selector"] == "input[name='username']"
    assert type_result["text"] == "admin"


def test_extract_from_page() -> None:
    data = _load_test_fixture()
    fixture = BrowserFixture(
        pages=data["pages"],
        responses=data.get("responses", {}),
    )
    stub = BrowserToolStub(fixtures_dir=str(BROWSER_TEST_FIXTURE.parent))
    stub._browser_fixtures["default"] = fixture

    title_result = stub.extract("title", "https://example.com/login")
    assert title_result["extracted"] == "Login"

    body_result = stub.extract("body", "https://example.com/dashboard")
    assert "Welcome, Admin" in body_result["extracted"]


def test_http_recording_and_replay() -> None:
    recording = HTTPRecording(cassette_dir="/tmp")

    request = {"method": "GET", "uri": "https://api.example.com/data", "headers": {}}
    response = {"status": 200, "headers": {}, "body": '{"items": [1, 2, 3]}'}
    recording.record("test_cassette", request, response)

    replayed = recording.replay("test_cassette", "https://api.example.com/data", "GET")
    assert replayed["status"] == 200
    assert replayed["body"] == '{"items": [1, 2, 3]}'


def test_cassette_save_load_roundtrip(tmp_path: Path) -> None:
    recording = HTTPRecording(cassette_dir=str(tmp_path))

    request = {"method": "POST", "uri": "https://api.example.com/login", "headers": {"Content-Type": "application/json"}}
    response = {"status": 200, "headers": {"Set-Cookie": "session=abc"}, "body": '{"token": "xyz"}'}
    recording.record("roundtrip", request, response)

    cassette_path = tmp_path / "roundtrip.json"
    recording.save_cassette("roundtrip", str(cassette_path))

    new_recording = HTTPRecording(cassette_dir=str(tmp_path))
    name = new_recording.load_cassette(str(cassette_path))
    assert name == "roundtrip"

    replayed = new_recording.replay("roundtrip", "https://api.example.com/login", "POST")
    assert replayed["status"] == 200
    assert replayed["body"] == '{"token": "xyz"}'


def test_integration_with_tool_stub(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "search.json").write_text(json.dumps({"results": ["a", "b"]}))

    browser_fixture_data = {
        "pages": {
            "https://example.com": "<html><title>Test</title></html>",
        },
        "responses": {
            "GET /api/status": {"status": 200, "body": {"ok": True}},
        },
    }
    (fixtures_dir / "http_browser.json").write_text(json.dumps(browser_fixture_data))

    stub = BrowserToolStub(fixtures_dir=str(fixtures_dir))

    tool_result = stub.intercept("search", {"query": "test"})
    assert tool_result == {"results": ["a", "b"]}

    nav = stub.navigate("https://example.com")
    assert nav["url"] == "https://example.com"
    assert "Test" in nav["html"]

    resp = stub.http_response("GET", "/api/status")
    assert resp["status"] == 200


def test_missing_browser_fixture_error(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    stub = BrowserToolStub(fixtures_dir=str(fixtures_dir))

    with pytest.raises(FixtureNotFoundError, match="No browser fixture named"):
        stub.navigate("https://example.com")


def test_multi_page_browser_fixture(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    data = _load_test_fixture()
    fixture = BrowserFixture(
        pages=data["pages"],
        cookies=data.get("cookies", {}),
        local_storage=data.get("local_storage", {}),
        responses=data.get("responses", {}),
    )

    stub = BrowserToolStub(fixtures_dir=str(fixtures_dir))
    stub._browser_fixtures["default"] = fixture

    pages = stub.available_pages()
    assert "https://example.com/login" in pages
    assert "https://example.com/dashboard" in pages
    assert len(pages) == 2

    nav1 = stub.navigate("https://example.com/login")
    assert "Login" in nav1["content"]

    nav2 = stub.navigate("https://example.com/dashboard")
    assert "session" in nav2["cookies"]
    assert nav2["cookies"]["session"] == "sess_abc123"
    assert nav2["local_storage"] == {"theme": "dark", "last_visit": "2025-01-01"}


def test_http_recording_missing_cassette(tmp_path: Path) -> None:
    recording = HTTPRecording(cassette_dir=str(tmp_path))

    with pytest.raises(KeyError, match="No cassette named"):
        recording.replay("nonexistent", "https://example.com", "GET")


def test_screen_capture_placeholder() -> None:
    data = _load_test_fixture()
    fixture = BrowserFixture(pages=data["pages"])
    stub = BrowserToolStub(fixtures_dir=str(BROWSER_TEST_FIXTURE.parent))
    stub._browser_fixtures["default"] = fixture

    capture = stub.screen_capture()
    assert capture["action"] == "screen_capture"
    assert capture["screenshot"] == "base64-placeholder"
    assert capture["format"] == "png"
