(function () {
  "use strict";

  // Runs only inside the Group room's preview modal. The room page posts the
  // uploaded HTML here; this page's frame-src 'none' CSP is inherited by the
  // nested srcdoc frame, so opt-in scripts cannot navigate it to another URL.
  if (window.parent === window) return;
  const frame = document.getElementById("html-preview");
  const renderer = window.FSQRHtmlPreviewRenderer.create(window.HTML_PREVIEW_CDN);
  let currentVersion = 0;

  function report(state, version) {
    window.parent.postMessage({ type: "html-preview", state, version }, location.origin);
  }

  window.addEventListener("message", async function (event) {
    const data = event.data;
    if (event.source === window.parent && event.origin === location.origin &&
        data?.type === "group-html-render") {
      if (typeof data.source !== "string" || !Number.isInteger(data.version)) return;
      currentVersion = data.version;
      try {
        const html = await renderer.build(data.source, data.scriptsEnabled === true, data.version);
        if (data.version !== currentVersion) return;
        frame.srcdoc = html;
        frame.hidden = false;
      } catch (_) {
        if (data.version === currentVersion) report("error", data.version);
      }
      return;
    }
    if (event.source === frame.contentWindow && data?.type === "html-preview" &&
        data.version === currentVersion) {
      report(data.state === "cdn-error" ? "cdn-error" : "ready", currentVersion);
    }
  });
  report("viewer-ready", 0);
})();
