(function () {
  "use strict";

  const source = document.getElementById("html-source");
  const frame = document.getElementById("html-preview");
  const empty = document.getElementById("preview-empty");
  const status = document.getElementById("preview-status");
  const workspace = document.querySelector(".workspace");
  const sourceButton = document.getElementById("show-source");
  const previewButton = document.getElementById("show-preview");
  const renderer = window.FSQRHtmlPreviewRenderer.create(window.HTML_PREVIEW_CDN);
  const executeScripts = document.getElementById("execute-scripts");
  const previewPanel = document.getElementById("preview-panel");
  const stage = previewPanel.querySelector(".preview-stage");
  const fullscreenButton = document.getElementById("toggle-fullscreen");
  const sampleButton = document.getElementById("insert-sample");
  const clearButton = document.getElementById("clear-source");
  const widthButtons = document.querySelectorAll("[data-preview-width]");
  const desktop = window.matchMedia("(min-width: 768px)");
  let renderVersion = 0;
  let autoRenderTimer = 0;

  function showView(view, moveFocus) {
    workspace.dataset.view = view;
    sourceButton.setAttribute("aria-pressed", String(view === "source"));
    previewButton.setAttribute("aria-pressed", String(view === "preview"));
    if (moveFocus && window.matchMedia("(max-width: 767px)").matches) {
      (view === "source" ? source : previewButton).focus();
    }
  }

  sourceButton.addEventListener("click", function () { showView("source", true); });
  previewButton.addEventListener("click", function () { showView("preview", false); });
  window.addEventListener("message", function (event) {
    if (event.source !== frame.contentWindow || event.data?.type !== "html-preview" ||
        event.data.version !== renderVersion) return;
    if (Number.isFinite(event.data.height)) {
      frame.style.height = Math.min(3000, Math.max(320, event.data.height)) + "px";
    }
    if (event.data.state === "ready") status.textContent = status.dataset.ready;
    if (event.data.state === "cdn-error") status.textContent = status.dataset.cdnError;
  });
  // Typing on wide screens refreshes the preview without moving focus or views.
  // Opt-in scripts only rerun when the user presses the button.
  async function renderPreview(showResult) {
    const version = ++renderVersion;
    try {
      if (showResult) frame.style.height = "";
      if (!source.value.trim()) {
        frame.removeAttribute("srcdoc");
        frame.hidden = true;
        empty.hidden = false;
        status.textContent = "";
      } else {
        if (showResult) {
          status.textContent = status.dataset.loading;
          showView("preview", true);
        }
        const html = await renderer.build(source.value, executeScripts.checked, version);
        if (version !== renderVersion) return;
        frame.srcdoc = html;
        frame.hidden = false;
        empty.hidden = true;
      }
      if (showResult) showView("preview", true);
    } catch (_) {
      if (version !== renderVersion) return;
      status.textContent = status.dataset.error;
      if (showResult) showView("preview", true);
    }
  }

  function updateSourceActions() {
    const hasSource = source.value.length > 0;
    sampleButton.disabled = hasSource;
    clearButton.disabled = !hasSource;
  }

  function setFullscreen(active) {
    previewPanel.classList.toggle("is-fullscreen", active);
    document.documentElement.classList.toggle("preview-fullscreen", active);
    fullscreenButton.querySelector("span").textContent =
      active ? fullscreenButton.dataset.exit : fullscreenButton.dataset.enter;
  }

  document.getElementById("render-preview").addEventListener("click", function () {
    clearTimeout(autoRenderTimer);
    renderPreview(true);
  });
  source.addEventListener("input", function () {
    updateSourceActions();
    clearTimeout(autoRenderTimer);
    if (desktop.matches && !executeScripts.checked) {
      autoRenderTimer = setTimeout(function () {
        if (!executeScripts.checked) renderPreview(false);
      }, 700);
    }
  });
  sampleButton.addEventListener("click", function () {
    source.value = document.getElementById("html-sample").textContent;
    updateSourceActions();
    renderPreview(true);
  });
  clearButton.addEventListener("click", function () {
    clearTimeout(autoRenderTimer);
    source.value = "";
    updateSourceActions();
    renderPreview(false);
    source.focus();
  });
  for (const button of widthButtons) {
    button.addEventListener("click", function () {
      stage.dataset.width = button.dataset.previewWidth;
      for (const other of widthButtons) {
        other.setAttribute("aria-pressed", String(other === button));
      }
    });
  }
  // Without the Fullscreen API (iPhone), the panel stays a fixed overlay.
  function closeFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else setFullscreen(false);
  }
  fullscreenButton.addEventListener("click", function () {
    if (previewPanel.classList.contains("is-fullscreen")) {
      closeFullscreen();
    } else {
      setFullscreen(true);
      previewPanel.requestFullscreen?.().catch(function () {});
    }
  });
  document.addEventListener("fullscreenchange", function () {
    if (!document.fullscreenElement) setFullscreen(false);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && previewPanel.classList.contains("is-fullscreen")) {
      closeFullscreen();
      fullscreenButton.focus();
    }
  });
})();
