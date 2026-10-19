"""Optional browser regressions; install Playwright + Chromium locally to run."""

import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import httpx
import pytest

from HtmlPreview.html_preview_app import CDN_ASSETS

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    f"/static/{name}": ROOT / "static" / name
    for name in (
        "css/00-breakpoints.css",
        "css/html-preview.css",
        "js/html_preview/preview.js",
        "favicon.ico",
    )
}


@pytest.fixture(scope="module")
def preview_url(test_client):
    response = test_client.get("/html-preview?lang=en")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/html-preview":
                body = response.content
                content_type = "text/html; charset=utf-8"
            elif path in ASSETS:
                asset = ASSETS[path]
                body = asset.read_bytes()
                content_type = guess_type(asset)[0] or "application/octet-stream"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header(
                "Content-Security-Policy", response.headers["content-security-policy"]
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/html-preview"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def browser_page(preview_url):
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(preview_url, wait_until="networkidle")
        yield page
        browser.close()


def render(page, html):
    if not page.locator("#html-source").is_visible():
        page.locator("#show-source").click()
    page.locator("#html-source").fill(html)
    page.locator("#render-preview").click()
    return page.frame_locator("#html-preview")


def test_browser_fixture_only_serves_tool_assets(browser_page):
    page = browser_page
    for path in ("/AGENTS.md", "/static/style.css", "/static/../README.md"):
        response = page.request.get(page.url.replace("/html-preview", path))
        assert response.status == 404


def test_preview_renders_styles_and_replaces_content(browser_page):
    page = browser_page
    frame = render(
        page,
        "<!doctype html><html><head><style>h1{color:rgb(12,34,56)}</style>"
        "</head><body><h1>Example</h1><p>Hello</p>"
        "<table><tr><td>Cell</td></tr></table></body></html>",
    )
    playwright.expect(frame.locator("h1")).to_have_text("Example")
    playwright.expect(frame.locator("h1")).to_have_css("color", "rgb(12, 34, 56)")
    playwright.expect(frame.locator("td")).to_have_text("Cell")
    frame = render(page, "<p>New content</p>")
    playwright.expect(frame.locator("p")).to_have_text("New content")
    playwright.expect(frame.locator("h1")).to_have_count(0)
    render(page, " ")
    playwright.expect(page.locator("#html-preview")).to_be_hidden()
    playwright.expect(page.locator("#preview-empty")).to_be_visible()


def test_preview_does_not_execute_or_send_pasted_content(browser_page):
    page = browser_page
    requests = []

    def capture_network_request(route):
        requests.append(route.request.url)
        route.abort()

    # A request event also fires for CSP-blocked attempts. Routing observes
    # requests that could actually leave the browser after CSP enforcement.
    page.context.route("**/*", capture_network_request)
    frame = render(
        page,
        '<meta http-equiv="refresh" content="0;url=/leak-refresh">'
        '<base href="https://example.invalid/">'
        '<script>parent.document.body.dataset.compromised="yes";'
        'fetch("/leak-script")</script>'
        '<link rel="stylesheet" href="/leak-link">'
        '<style>@import url("/leak-css"); p{background:url(/leak-bg)}</style>'
        f'<style>@import url("{CDN_ASSETS["styles"][0]["url"]}");</style>'
        '<img src="/leak-img" srcset="/leak-srcset 2x" onerror="alert(1)">'
        '<iframe src="/leak-frame"></iframe>'
        '<svg><image href="/leak-svg"/></svg>'
        '<object data="/leak-object"></object>'
        '<a href="/leak-navigation" ping="/leak-ping" target="_top">Link</a>'
        '<input type="image" src="/leak-input">'
        '<form action="/leak-form"><input name="secret" value="private">'
        '<button type="submit">Submit</button></form>'
        '<p style="background-image:url(https://example.invalid/leak)">Safe</p>',
    )
    playwright.expect(frame.locator("p")).to_have_text("Safe")
    frame.locator("a").click()
    playwright.expect(frame.locator("form button")).to_be_disabled()
    playwright.expect(frame.locator("input[name]")).to_have_count(0)
    page.wait_for_timeout(250)
    assert requests == []
    assert page.evaluate("document.body.dataset.compromised") is None
    assert page.evaluate("localStorage.length") == 0
    assert page.evaluate("sessionStorage.length") == 0
    assert page.url.endswith("/html-preview")
    frame_url = page.frames[1].url
    assert frame_url == "about:srcdoc"


def test_preview_works_offline_and_reload_clears_input(browser_page):
    page = browser_page
    page.context.set_offline(True)
    frame = render(page, "<h2>Offline</h2>")
    playwright.expect(frame.locator("h2")).to_have_text("Offline")
    page.context.set_offline(False)
    page.reload(wait_until="networkidle")
    playwright.expect(page.locator("#html-source")).to_have_value("")
    playwright.expect(page.locator("#preview-empty")).to_be_visible()


def test_preview_scrolls_local_anchors_without_navigation(browser_page):
    page = browser_page
    requests = []
    page.context.route(
        "**/*", lambda route: (requests.append(route.request.url), route.abort())
    )
    frame = render(
        page,
        '<a href="#%E7%9B%AE%E6%AC%A1">Jump</a>'
        '<a href="https://example.invalid/#target">External</a>'
        '<a href="#%ZZ">Malformed</a>'
        '<div style="height:4000px"></div><h2 id="目次">Destination</h2>',
    )
    link = frame.get_by_role("link", name="Jump", exact=True)
    playwright.expect(link).to_have_attribute("tabindex", "0")
    link.click()
    assert page.frames[1].evaluate("scrollY") > 0
    page.frames[1].evaluate("scrollTo(0, 0)")
    link.focus()
    link.press("Enter")
    assert page.frames[1].evaluate("scrollY") > 0
    playwright.expect(frame.locator("a[href]")).to_have_count(0)
    playwright.expect(frame.get_by_role("link")).to_have_count(1)
    assert page.frames[1].url == "about:srcdoc"
    assert requests == []


def test_preview_loads_only_approved_styles_with_integrity(browser_page):
    page = browser_page
    asset = CDN_ASSETS["styles"][0]
    requests = []

    def stylesheet(route):
        requests.append(route.request.url)
        route.fulfill(
            body=(ROOT / "static" / "bootstrap.min.css").read_bytes(),
            content_type="text/css",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    page.context.route(asset["url"], stylesheet)
    frame = render(
        page,
        f'<link rel="stylesheet" href="{asset["url"]}">'
        '<link rel="stylesheet" href="https://example.invalid/untrusted.css">'
        '<div class="d-flex"><p class="text-primary">Bootstrap</p></div>'
        f'<script src="{CDN_ASSETS["mermaid"]["url"]}"></script>',
    )
    playwright.expect(frame.locator("div")).to_have_css("display", "flex")
    playwright.expect(page.locator("#preview-status")).to_have_text("Preview updated.")
    assert requests == [asset["url"]]
    playwright.expect(frame.locator("link")).to_have_count(0)


def test_preview_reports_modified_or_unavailable_cdn(browser_page):
    page = browser_page
    asset = CDN_ASSETS["styles"][0]
    page.context.route(
        asset["url"],
        lambda route: route.fulfill(
            body="body{color:red}",
            content_type="text/css",
            headers={"Access-Control-Allow-Origin": "*"},
        ),
    )
    render(page, f'<link rel="stylesheet" href="{asset["url"]}"><p>Safe</p>')
    playwright.expect(page.locator("#preview-status")).to_have_text(
        "A CDN could not load or Mermaid could not render. "
        "Check your connection and diagram syntax."
    )


def test_preview_expands_to_fit_tall_content(browser_page):
    page = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    render(page, '<div style="height:1200px">Tall preview</div>')
    playwright.expect(page.locator("#preview-status")).to_have_text("Preview updated.")
    assert page.locator("#html-preview").bounding_box()["height"] >= 1200


@pytest.fixture(scope="module")
def mermaid_bundle():
    # Optional browser tests require internet for the pinned upstream bundle.
    response = httpx.get(CDN_ASSETS["mermaid"]["url"], timeout=45)
    response.raise_for_status()
    return response.content


def test_preview_renders_real_mermaid_and_reports_bad_syntax(
    browser_page, mermaid_bundle
):
    page = browser_page
    page.context.route(
        CDN_ASSETS["mermaid"]["url"],
        lambda route: route.fulfill(
            body=mermaid_bundle,
            content_type="text/javascript",
            headers={"Access-Control-Allow-Origin": "*"},
        ),
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    frame = render(
        page,
        '<pre class="mermaid">graph TD\n A[Start] --> B[Finish]</pre>'
        '<script>parent.document.body.dataset.compromised="yes"</script>',
    )
    playwright.expect(frame.locator(".mermaid svg")).to_be_visible(timeout=15000)
    playwright.expect(frame.locator(".mermaid svg")).to_contain_text("Start")
    playwright.expect(page.locator("#preview-status")).to_have_text("Preview updated.")
    assert page.evaluate("document.body.dataset.compromised") is None
    assert errors == []
    page.set_viewport_size({"width": 390, "height": 844})
    frame = render(
        page,
        '<pre class="mermaid">graph LR\n A[First long label] --> '
        "B[Second long label] --> C[Third long label]</pre>",
    )
    playwright.expect(frame.locator(".mermaid svg")).to_be_visible(timeout=15000)
    dimensions = frame.locator(".mermaid").evaluate(
        "e => ({visible:e.clientWidth, content:e.scrollWidth, "
        "page:e.ownerDocument.documentElement.scrollWidth, "
        "viewport:e.ownerDocument.documentElement.clientWidth})"
    )
    assert dimensions["content"] > dimensions["visible"]
    assert dimensions["page"] <= dimensions["viewport"]
    page.locator("#show-source").click()
    render(page, '<pre class="mermaid">invalid diagram syntax</pre>')
    playwright.expect(page.locator("#preview-status")).to_have_text(
        "A CDN could not load or Mermaid could not render. "
        "Check your connection and diagram syntax."
    )


@pytest.mark.parametrize("width,height", [(1280, 800), (390, 844), (320, 640)])
def test_preview_responsive_switching(browser_page, width, height):
    page = browser_page
    page.set_viewport_size({"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    frame = render(page, "<h1>Preview</h1><p>Readable on mobile and desktop.</p>")
    playwright.expect(frame.locator("h1")).to_have_text("Preview")
    if width < 768:
        playwright.expect(page.locator("#source-panel")).to_be_hidden()
        playwright.expect(page.locator("#show-preview")).to_be_focused()
        page.locator("#show-source").click()
        playwright.expect(page.locator("#html-source")).to_be_focused()
        playwright.expect(page.locator("#preview-panel")).to_be_hidden()
        page.locator("#show-preview").click()
    else:
        playwright.expect(page.locator("#source-panel")).to_be_visible()
    assert (
        page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        == 0
    )
    assert errors == []


def test_sample_and_clear_controls(browser_page):
    page = browser_page
    playwright.expect(page.locator("#clear-source")).to_be_disabled()
    page.locator("#insert-sample").click()
    frame = page.frame_locator("#html-preview")
    playwright.expect(frame.locator("h1")).to_have_text("Sample page")
    playwright.expect(page.locator("#insert-sample")).to_be_disabled()
    page.locator("#clear-source").click()
    playwright.expect(page.locator("#html-source")).to_have_value("")
    playwright.expect(page.locator("#html-source")).to_be_focused()
    playwright.expect(page.locator("#html-preview")).to_be_hidden()
    playwright.expect(page.locator("#preview-empty")).to_be_visible()
    playwright.expect(page.locator("#insert-sample")).to_be_enabled()


def test_preview_follows_typing_only_on_wide_screens_without_scripts(browser_page):
    page = browser_page
    page.locator("#html-source").fill("<h1>Typed</h1>")
    playwright.expect(page.frame_locator("#html-preview").locator("h1")).to_have_text(
        "Typed"
    )
    playwright.expect(page.locator("#html-source")).to_be_focused()
    page.locator("#execute-scripts").check()
    page.locator("#html-source").fill("<h1>Script mode</h1>")
    page.wait_for_timeout(1200)
    assert "Script mode" not in page.locator("#html-preview").get_attribute("srcdoc")
    page.locator("#execute-scripts").uncheck()
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator("#html-source").fill("<h1>Phone</h1>")
    page.wait_for_timeout(1200)
    assert "Phone" not in page.locator("#html-preview").get_attribute("srcdoc")
    playwright.expect(page.locator("#source-panel")).to_be_visible()


def test_preview_width_switch_and_fullscreen(browser_page):
    page = browser_page
    frame = render(page, "<h1>Width</h1>")
    playwright.expect(frame.locator("h1")).to_have_text("Width")
    page.locator('[data-preview-width="mobile"]').click()
    playwright.expect(page.locator('[data-preview-width="mobile"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    assert frame.locator("body").evaluate("() => innerWidth") == 390
    page.locator('[data-preview-width="tablet"]').click()
    assert frame.locator("body").evaluate("() => innerWidth") == 768
    button = page.locator("#toggle-fullscreen")
    button.click()
    playwright.expect(button).to_have_text("Exit full screen")
    box = page.locator("#preview-panel").bounding_box()
    assert (box["x"], box["y"], box["width"], box["height"]) == (0, 0, 1280, 800)
    button.click()
    playwright.expect(button).to_have_text("Full screen")
    playwright.expect(page.locator("#preview-panel")).not_to_have_class(
        re.compile("is-fullscreen")
    )
    assert page.evaluate("document.fullscreenElement") is None
    page.set_viewport_size({"width": 390, "height": 844})
    assert frame.locator("body").evaluate("() => innerWidth") <= 390


def test_fullscreen_fallback_covers_page_and_closes_with_escape(browser_page):
    page = browser_page
    page.evaluate("delete Element.prototype.requestFullscreen")
    render(page, "<h1>Fallback</h1>")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.locator("#toggle-fullscreen").click()
    playwright.expect(page.locator("#preview-panel")).to_have_class(
        re.compile("is-fullscreen")
    )
    assert page.evaluate("document.fullscreenElement") is None
    covered = page.evaluate(
        "() => [[640, 790], [640, 400]].every(([x, y]) => "
        "document.getElementById('preview-panel')"
        ".contains(document.elementFromPoint(x, y)))"
    )
    assert covered
    page.keyboard.press("Escape")
    playwright.expect(page.locator("#preview-panel")).not_to_have_class(
        re.compile("is-fullscreen")
    )
    playwright.expect(page.locator("#toggle-fullscreen")).to_be_focused()


def test_opt_in_scripts_run_without_parent_storage_or_network_access(browser_page):
    page = browser_page
    requests = []
    page.context.route(
        "**/*", lambda route: (requests.append(route.request.url), route.abort())
    )
    page.locator("#execute-scripts").check()
    frame = render(
        page,
        '<button id="increment">Add</button><p id="count" data-n="4"></p>'
        '<script>const count=document.getElementById("count");'
        "count.textContent=count.dataset.n;"
        'document.getElementById("increment").onclick=()=>count.textContent++;'
        'try{parent.document.body.dataset.compromised="yes"}catch(e){}'
        'try{localStorage.setItem("private","value")}catch(e){}'
        'fetch("/leak-script").catch(()=>{});'
        'fetch("https://example.invalid/leak").catch(()=>{});'
        'const s=document.createElement("script");s.nonce=document.currentScript.nonce;'
        's.src="/leak-nonce";document.head.appendChild(s);'
        'const img=new Image();img.src="/leak-image";'
        "</script>",
    )
    playwright.expect(frame.locator("#count")).to_have_text("4")
    frame.get_by_role("button", name="Add").click()
    playwright.expect(frame.locator("#count")).to_have_text("5")
    page.wait_for_timeout(100)
    assert requests == []
    assert page.evaluate("document.body.dataset.compromised") is None
    assert page.evaluate("localStorage.length + sessionStorage.length") == 0
    page.context.unroute("**/*")
    page.reload()
    playwright.expect(page.locator("#execute-scripts")).not_to_be_checked()


def test_opt_in_scripts_can_use_preloaded_real_mermaid(browser_page, mermaid_bundle):
    page = browser_page
    page.context.route(
        CDN_ASSETS["mermaid"]["url"],
        lambda route: route.fulfill(
            body=mermaid_bundle,
            content_type="text/javascript",
            headers={"Access-Control-Allow-Origin": "*"},
        ),
    )
    page.locator("#execute-scripts").check()
    frame = render(
        page,
        '<pre class="mermaid">graph TD\n A[Start] --> B[Finish]</pre>'
        '<script>mermaid.initialize({startOnLoad:false,securityLevel:"loose"});'
        'mermaid.run({nodes:document.querySelectorAll(".mermaid")});</script>',
    )
    playwright.expect(frame.locator(".mermaid svg")).to_contain_text(
        "Start", timeout=15000
    )
    playwright.expect(page.locator("#preview-status")).to_have_text("Preview updated.")
    assert (
        page.frames[1].evaluate("mermaid.mermaidAPI.getConfig().securityLevel")
        == "strict"
    )


@pytest.mark.parametrize(
    "destination", ["/html-preview?leak=private", "https://example.invalid/leak"]
)
def test_opt_in_scripts_cannot_navigate_to_send_content(browser_page, destination):
    page = browser_page
    requests = []
    page.context.route(
        "**/*", lambda route: (requests.append(route.request.url), route.abort())
    )
    page.locator("#execute-scripts").check()
    render(page, f'<p>Private</p><script>location.href="{destination}"</script>')
    page.wait_for_timeout(150)
    assert requests == []
    assert page.url.endswith("/html-preview")


@pytest.mark.parametrize("scripts_enabled", [False, True])
def test_approved_google_font_is_pinned_and_bad_integrity_keeps_html(
    browser_page, scripts_enabled
):
    page = browser_page
    font = CDN_ASSETS["webfonts"][1]
    requests = []

    def modified_font(route):
        requests.append(route.request.url)
        route.fulfill(
            body=b"modified font",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    page.context.route("**/*", modified_font)
    page.locator("#execute-scripts").set_checked(scripts_enabled)
    frame = render(
        page,
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=JetBrains+Mono:wght@400;600&amp;display=swap">'
        "<p>Readable fallback</p>",
    )
    playwright.expect(frame.locator("p")).to_have_text("Readable fallback")
    playwright.expect(page.locator("#preview-status")).to_have_text(
        "A CDN could not load or Mermaid could not render. "
        "Check your connection and diagram syntax."
    )
    assert requests == [font["url"]]


def test_opt_in_styles_are_loaded_by_parent_with_integrity(browser_page):
    page = browser_page
    asset = CDN_ASSETS["styles"][0]
    requests = []

    def stylesheet(route):
        requests.append(route.request.frame.parent_frame)
        route.fulfill(
            body=(ROOT / "static" / "bootstrap.min.css").read_bytes(),
            content_type="text/css",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    page.context.route(asset["url"], stylesheet)
    page.locator("#execute-scripts").check()
    frame = render(
        page,
        f'<link rel="stylesheet" href="{asset["url"]}">'
        '<div class="d-flex">Bootstrap</div>',
    )
    playwright.expect(frame.locator("div")).to_have_css("display", "flex")
    assert requests == [None]
