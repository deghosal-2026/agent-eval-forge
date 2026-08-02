"""Browser automation fixtures for deterministic web interaction testing.

Provides :class:`BrowserFixture` for storing page HTML, cookies, and responses,
and :class:`BrowserToolStub` for intercepting browser tool calls with fixture
data instead of live browser automation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evalforge.fixtures.tool_stub import FixtureNotFoundError, ToolStub


@dataclass
class BrowserFixture:
    """Fixture data for a single browser session or page state.

    Attributes:
        pages: Mapping of URL → HTML content.
        cookies: Mapping of URL → cookie data.
        local_storage: Mapping of URL → local storage key-value data.
        responses: Mapping of ``"METHOD URL"`` → response dicts.
    """

    pages: dict[str, str]
    cookies: dict[str, str] = field(default_factory=dict)
    local_storage: dict[str, dict[str, Any]] = field(default_factory=dict)
    responses: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_page(self, url: str) -> str:
        """Get the fixture HTML for a URL.

        Args:
            url: The URL to look up.

        Returns:
            The HTML content string.

        Raises:
            FixtureNotFoundError: If no page fixture exists for the URL.
        """
        if url not in self.pages:
            raise FixtureNotFoundError(
                f"No page fixture for URL '{url}'"
            )
        return self.pages[url]

    def get_page_content(self, url: str) -> str:
        """Get the text content of a page fixture (HTML tags stripped).

        Args:
            url: The URL to look up.

        Returns:
            The page text with all HTML tags removed.
        """
        html = self.get_page(url)
        return re.sub(r"<[^>]+>", " ", html).strip()

    def get_response(self, method: str, url: str) -> dict[str, Any]:
        """Get a fixture HTTP response for a method+URL combination.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: The request URL.

        Returns:
            The response dict.

        Raises:
            FixtureNotFoundError: If no response fixture exists.
        """
        key = f"{method.upper()} {url}"
        if key not in self.responses:
            raise FixtureNotFoundError(
                f"No response fixture for '{key}'"
            )
        return self.responses[key]


class BrowserToolStub:
    """Intercepts browser automation tool calls with fixture data.

    Wraps a :class:`ToolStub` for generic tool interception and adds
    browser-specific methods (navigate, click, type_text, extract,
    screen_capture) that return structured fixture responses.

    Browser fixtures are loaded from ``http_browser.json`` in the fixtures
    directory, which can contain a single fixture or a list of named fixtures.
    """

    def __init__(self, fixtures_dir: str = "scenarios/fixtures") -> None:
        """Initialize the browser tool stub.

        Args:
            fixtures_dir: Directory containing fixture files, including
                ``http_browser.json``.
        """
        self._tool_stub = ToolStub(fixtures_dir)
        self._browser_fixtures: dict[str, BrowserFixture] = {}
        self._load_browser_fixtures()

    def _load_browser_fixtures(self) -> None:
        """Load browser fixtures from the ``http_browser.json`` file.

        Supports both a single fixture dict (keyed as ``"default"``) and
        a list of named fixtures with a ``"name"`` field.
        """
        browser_path = Path(self._tool_stub._fixtures_dir) / "http_browser.json"
        if not browser_path.exists():
            return
        data = json.loads(browser_path.read_text())
        if isinstance(data, dict) and "pages" in data:
            fixture = BrowserFixture(
                pages=data.get("pages", {}),
                cookies=data.get("cookies", {}),
                local_storage=data.get("local_storage", {}),
                responses=data.get("responses", {}),
            )
            self._browser_fixtures["default"] = fixture
        elif isinstance(data, list):
            for entry in data:
                name = entry.get("name", "default")
                fixture = BrowserFixture(
                    pages=entry.get("pages", {}),
                    cookies=entry.get("cookies", {}),
                    local_storage=entry.get("local_storage", {}),
                    responses=entry.get("responses", {}),
                )
                self._browser_fixtures[name] = fixture

    def _get_fixture(self, name: str = "default") -> BrowserFixture:
        """Get a named browser fixture.

        Args:
            name: The fixture name (defaults to ``"default"``).

        Returns:
            The :class:`BrowserFixture` instance.

        Raises:
            FixtureNotFoundError: If no such named fixture exists.
        """
        if name not in self._browser_fixtures:
            raise FixtureNotFoundError(
                f"No browser fixture named '{name}'"
            )
        return self._browser_fixtures[name]

    def navigate(self, url: str) -> dict[str, Any]:
        """Simulate a browser navigate action.

        Args:
            url: The URL to navigate to.

        Returns:
            A dict with ``url``, ``html``, ``content``, ``cookies``,
            and ``local_storage`` from the fixture.
        """
        fixture = self._get_fixture()
        html = fixture.get_page(url)
        content = fixture.get_page_content(url)
        cookies: Any = fixture.cookies.get(url, {})
        storage = fixture.local_storage.get(url, {})
        return {
            "url": url,
            "html": html,
            "content": content,
            "cookies": cookies,
            "local_storage": storage,
        }

    def click(self, selector: str, current_url: str) -> dict[str, Any]:
        """Simulate a browser click action.

        Args:
            selector: The CSS selector to click.
            current_url: The current page URL.

        Returns:
            A dict with the action metadata and current page HTML.
        """
        fixture = self._get_fixture()
        html = fixture.get_page(current_url)
        return {
            "action": "click",
            "selector": selector,
            "url": current_url,
            "html": html,
        }

    def type_text(self, selector: str, text: str) -> dict[str, Any]:
        """Simulate a browser type/text-input action.

        Args:
            selector: The CSS selector for the input element.
            text: The text to type.

        Returns:
            A dict with the action metadata.
        """
        return {
            "action": "type",
            "selector": selector,
            "text": text,
        }

    def extract(self, selector: str, current_url: str) -> dict[str, Any]:
        """Simulate extracting content from the current page.

        Supports special selectors ``"title"`` and ``"body"`` for common
        extraction patterns.

        Args:
            selector: The CSS selector (or ``"title"`` / ``"body"``).
            current_url: The current page URL.

        Returns:
            A dict with the extracted content.
        """
        fixture = self._get_fixture()
        html = fixture.get_page(current_url)
        if selector == "title":
            match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
            extracted = match.group(1) if match else ""
        elif selector == "body":
            extracted = fixture.get_page_content(current_url)
        else:
            extracted = html
        return {
            "action": "extract",
            "selector": selector,
            "url": current_url,
            "extracted": extracted,
        }

    def screen_capture(self) -> dict[str, Any]:
        """Simulate a browser screenshot capture.

        Returns:
            A dict with a placeholder base64 screenshot string.
        """
        return {
            "action": "screen_capture",
            "screenshot": "base64-placeholder",
            "format": "png",
            "width": 1280,
            "height": 720,
        }

    def http_response(self, method: str, url: str) -> dict[str, Any]:
        """Get a fixture HTTP response for a method+URL combination.

        Args:
            method: HTTP method.
            url: The request URL.

        Returns:
            The fixture HTTP response dict.
        """
        fixture = self._get_fixture()
        return fixture.get_response(method, url)

    def available_pages(self) -> set[str]:
        """Get all URLs that have fixture pages available.

        Returns:
            A set of URL strings.
        """
        fixture = self._get_fixture()
        return set(fixture.pages.keys())

    def intercept(self, tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generic tool call interception, delegated to the underlying ToolStub.

        Args:
            tool_name: The tool name to intercept.
            payload: Optional tool call payload.

        Returns:
            A fixture response dict.
        """
        return self._tool_stub.intercept(tool_name, payload)
