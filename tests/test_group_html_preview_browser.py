"""Optional browser regressions; install Playwright + Chromium locally to run."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import AsyncMock, patch

import pytest

playwright = pytest.importorskip("playwright.sync_api")

ROOM_ID = "abc123"
FORWARDED_HEADERS = (
    "content-type",
    "content-security-policy",
    "x-content-type-options",
    "cache-control",
)
PAGE_HTML = (
    "<h1 style='color:rgb(12,34,56)'>Hello</h1>"
    "<script>document.body.dataset.ran='yes';"
    "try{parent.document.body.dataset.compromised='yes'}catch(_){}"
    "try{localStorage.setItem('leak','1')}catch(_){document.body.dataset.storage='blocked'}"
    "fetch('/leak-script').catch(()=>{});"
    "try{top.location='/leak-nav'}catch(_){}</script>"
)


@pytest.fixture(scope="module")
def room_url(test_client, tmp_path_factory):
    uploads = tmp_path_factory.mktemp("group_uploads")
    room_dir = uploads / ROOM_ID
    room_dir.mkdir()
    (room_dir / "page.html").write_text(PAGE_HTML, encoding="utf-8")
    (room_dir / "large.htm").write_bytes(b"<p>large</p>" * 100)
    room = {"id": ROOM_ID, "retention_hours": 24, "time": None}

    class Handler(BaseHTTPRequestHandler):
        # The app under test answers every request, including static assets.
        def do_GET(self):
            response = test_client.get(self.path)
            body = response.content
            self.send_response(response.status_code)
            for name in FORWARDED_HEADERS:
                if name in response.headers:
                    self.send_header(name, response.headers[name])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # The browser test aborted or replaced this request.

        def log_message(self, *_args):
            pass

    with (
        patch(
            "Group.group_routes_room.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Group.group_routes_room.get_room_if_active",
            new_callable=AsyncMock,
            return_value=room,
        ),
        patch("Group.group_routes_room.has_group_room_access", return_value=True),
        patch("Group.group_routes_room.get_group_room_share_token", return_value=""),
        patch("Group.group_routes_room.register_success", new_callable=AsyncMock),
        patch(
            "Group.group_routes_file.get_room_if_active",
            new_callable=AsyncMock,
            return_value=room,
        ),
        patch("Group.group_routes_file.has_group_room_access", return_value=True),
        patch("Group.group_routes_file.UPLOAD_FOLDER", str(uploads)),
        patch("Group.group_routes_file.GROUP_HTML_PREVIEW_MAX_BYTES", 1000),
    ):
        # Serve one request at a time: the ASGI test client is not thread-safe.
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/group/r/{ROOM_ID}?lang=en"
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


@pytest.fixture
def room_page(room_url):
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        requests = []

        def capture(route):
            url = route.request.url
            if not url.startswith(room_url.split("/group/")[0]):
                route.abort()
                return
            requests.append(url)
            route.continue_()

        page.context.route("**/*", capture)
        page.goto(room_url, wait_until="domcontentloaded")
        page.requests = requests
        yield page
        browser.close()


def open_preview(page, filename):
    row = page.locator(".modern-file-item, li, tr").filter(has_text=filename).first
    row.get_by_role("button", name="Preview").click()
    playwright.expect(page.locator("#groupPreviewOverlay")).to_have_class(
        "group-preview-overlay is-visible"
    )


def test_html_opens_without_scripts(room_page):
    page = room_page
    open_preview(page, "page.html")
    frame = page.frame_locator("#groupPreviewBody iframe")
    playwright.expect(frame.locator("h1")).to_have_text("Hello")
    playwright.expect(frame.locator("h1")).to_have_css("color", "rgb(12, 34, 56)")
    iframe = page.locator("#groupPreviewBody iframe")
    assert iframe.get_attribute("sandbox") == "allow-scripts"
    assert frame.locator("body").get_attribute("data-ran") is None
    toggle = page.locator(".group-html-preview-toggle")
    playwright.expect(toggle).to_have_text("Run JavaScript")
    playwright.expect(toggle).to_have_attribute("aria-pressed", "false")


def test_opt_in_scripts_stay_isolated_and_stop(room_page):
    page = room_page
    open_preview(page, "page.html")
    toggle = page.locator(".group-html-preview-toggle")
    playwright.expect(toggle).to_have_text("Run JavaScript")
    toggle.click()
    frame = page.frame_locator("#groupPreviewBody iframe")
    playwright.expect(frame.locator("body")).to_have_attribute("data-ran", "yes")
    playwright.expect(frame.locator("body")).to_have_attribute(
        "data-storage", "blocked"
    )
    playwright.expect(toggle).to_have_text("Stop")
    assert page.locator("body").get_attribute("data-compromised") is None
    assert page.url.endswith(f"/group/r/{ROOM_ID}?lang=en")
    assert not [url for url in page.requests if "/leak" in url]

    toggle.click()
    playwright.expect(toggle).to_have_text("Run JavaScript")
    playwright.expect(frame.locator("h1")).to_have_text("Hello")
    assert frame.locator("body").get_attribute("data-ran") is None
    page.locator("#groupPreviewClose").click()
    playwright.expect(page.locator("#groupPreviewBody iframe")).to_have_count(0)


def test_reopening_resets_script_choice(room_page):
    page = room_page
    open_preview(page, "page.html")
    page.locator(".group-html-preview-toggle").click()
    playwright.expect(page.locator(".group-html-preview-toggle")).to_have_text("Stop")
    page.locator("#groupPreviewClose").click()
    open_preview(page, "page.html")
    playwright.expect(page.locator(".group-html-preview-toggle")).to_have_text(
        "Run JavaScript"
    )


def test_large_html_is_download_only(room_page):
    page = room_page
    open_preview(page, "large.htm")
    playwright.expect(page.locator(".group-preview-message")).to_contain_text(
        "too large"
    )
    playwright.expect(page.locator("#groupPreviewBody iframe")).to_have_count(0)


def test_direct_preview_url_is_not_rendered_as_page(room_page):
    page = room_page
    preview_url = page.url.split("/group/")[0] + f"/preview/{ROOM_ID}/page.html"
    response = page.goto(preview_url)
    assert response.headers["content-type"].startswith("text/plain")
    playwright.expect(page.locator("h1")).to_have_count(0)
    assert page.locator("body").get_attribute("data-ran") is None
