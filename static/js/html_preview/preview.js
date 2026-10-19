(function () {
  "use strict";

  const source = document.getElementById("html-source");
  const frame = document.getElementById("html-preview");
  const empty = document.getElementById("preview-empty");
  const status = document.getElementById("preview-status");
  const workspace = document.querySelector(".workspace");
  const sourceButton = document.getElementById("show-source");
  const previewButton = document.getElementById("show-preview");
  const nonce = document.currentScript.nonce;
  const cdn = window.HTML_PREVIEW_CDN;
  const executeScripts = document.getElementById("execute-scripts");
  const previewPanel = document.getElementById("preview-panel");
  const stage = previewPanel.querySelector(".preview-stage");
  const fullscreenButton = document.getElementById("toggle-fullscreen");
  const sampleButton = document.getElementById("insert-sample");
  const clearButton = document.getElementById("clear-source");
  const widthButtons = document.querySelectorAll("[data-preview-width]");
  const desktop = window.matchMedia("(min-width: 768px)");
  const assetCache = new Map();
  let renderVersion = 0;
  let autoRenderTimer = 0;

  // Parse in an inert template: pasted images must not be fetched while parsing.
  // Rebuild only HTML elements and display attributes; never adopt untrusted nodes.
  const allowedTags = new Set((
    "a abbr address article aside b bdi bdo blockquote br button caption cite " +
    "code col colgroup data dd del details dfn dialog div dl dt em fieldset " +
    "figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr i img input " +
    "ins kbd label legend li main mark menu meter nav ol optgroup option output " +
    "p picture pre progress q rp rt ruby s samp section select small source span " +
    "strong style sub summary sup table tbody td textarea tfoot th thead time " +
    "tr u ul var wbr"
  ).split(" "));
  const allowedAttributes = new Set((
    "alt class id style title lang dir width height colspan rowspan scope " +
    "span start reversed value open datetime type placeholder checked selected " +
    "multiple rows cols size min max low high optimum label"
  ).split(" "));
  const controls = new Set(["button", "input", "select", "textarea", "option", "optgroup"]);
  const rasterData = /^data:image\/(?:png|jpeg|gif|webp|avif);base64,[a-z0-9+/=\s]+$/i;

  // In opt-in mode, CDN bytes are already verified and embedded by the parent.
  // The renderer runs inside the opaque sandbox in both modes.
  async function renderFrame(styles, mermaidAsset, version, scriptsEnabled, preloadFailed) {
    const rendererNonce = document.currentScript.nonce;
    // Scroll within this document without navigating srcdoc to the host URL.
    function followAnchor(event) {
      if (event.type === "keydown" && event.key !== "Enter") return;
      const link = event.target.closest("a[data-preview-target]");
      if (!link) return;
      event.preventDefault();
      const target = document.getElementById(link.dataset.previewTarget);
      if (target) target.scrollIntoView({ block: "start" });
    }
    document.addEventListener("click", followAnchor);
    document.addEventListener("keydown", followAnchor);
    const report = (state) => parent.postMessage({
      type: "html-preview", state, version,
      height: document.documentElement.scrollHeight
    }, "*");
    let failed = preloadFailed;
    const stylesReady = await Promise.allSettled(styles.map(async asset => {
      const response = await fetch(asset.url, {
        integrity: asset.integrity, mode: "cors", credentials: "omit", referrerPolicy: "no-referrer"
      });
      if (!response.ok) throw new Error("Stylesheet unavailable");
      const css = await response.text();
      const style = document.createElement("style");
      // Resolve the pinned stylesheet's relative font/data URLs before inlining.
      style.textContent = css.replace(/url\(\s*(["']?)(.*?)\1\s*\)/gi,
        (_match, _quote, url) => "url(" + JSON.stringify(new URL(url, asset.url).href) + ")");
      document.head.appendChild(style);
    }));
    failed ||= stylesReady.some(result => result.status === "rejected");
    const diagrams = document.querySelectorAll("pre.mermaid, div.mermaid");
    if (diagrams.length) {
      try {
        if (!scriptsEnabled) await new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = mermaidAsset.url;
          script.integrity = mermaidAsset.integrity;
          script.crossOrigin = "anonymous";
          script.referrerPolicy = "no-referrer";
          script.nonce = rendererNonce;
          script.onload = resolve;
          script.onerror = reject;
          document.head.appendChild(script);
        });
        const mermaid = window.mermaid;
        if (!scriptsEnabled) mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          maxTextSize: 50000,
          maxEdges: 500,
          suppressErrorRendering: true,
          fontFamily: "system-ui, sans-serif",
          flowchart: { htmlLabels: false },
          secure: ["secure", "securityLevel", "startOnLoad", "maxTextSize", "maxEdges",
            "suppressErrorRendering", "dompurifyConfig", "themeCSS", "fontFamily", "flowchart"]
        });
        if (scriptsEnabled) await window.previewMermaidReady;
        const pending = [...diagrams].filter(node => node.dataset.processed !== "true");
        if (pending.length) await mermaid.run({ nodes: pending });
        // Keep diagram labels readable on phones; wide diagrams scroll inside
        // their own container instead of shrinking the text to fit the screen.
        for (const diagram of diagrams) {
          const svg = diagram.querySelector("svg");
          if (svg?.viewBox.baseVal.width) {
            svg.style.width = Math.ceil(svg.viewBox.baseVal.width) + "px";
            svg.style.maxWidth = "none";
            svg.style.height = "auto";
          }
        }
      } catch (_) {
        failed = true;
      }
    }
    await document.fonts.ready;
    report(failed ? "cdn-error" : "ready");
    if (scriptsEnabled) new ResizeObserver(() => report(failed ? "cdn-error" : "ready"))
      .observe(document.body);
    // Static previews reflow when the parent switches the preview width.
    let lastWidth = innerWidth;
    if (!scriptsEnabled) addEventListener("resize", () => {
      if (innerWidth === lastWidth) return;
      lastWidth = innerWidth;
      report(failed ? "cdn-error" : "ready");
    });
  }

  function inlineScript(code) {
    return "<script nonce='" + nonce + "'>" + code.replace(/<\/script/gi, "<\\/script") + "</script>";
  }

  // Only the parent fetches approved assets. Executable previews receive bytes,
  // never network permissions or access to the parent's asset loader.
  function loadAsset(asset) {
    if (!assetCache.has(asset.url)) {
      const request = fetch(asset.url, {
        integrity: asset.integrity, mode: "cors", credentials: "omit", referrerPolicy: "no-referrer"
      }).then(response => {
        if (!response.ok) throw new Error("Asset unavailable");
        return response.blob();
      });
      assetCache.set(asset.url, request);
      request.catch(() => assetCache.delete(asset.url));
    }
    return assetCache.get(asset.url);
  }

  function asDataURL(blob) {
    return new Promise(resolve => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    });
  }

  async function prepareStyles(styles) {
    return Promise.all(styles.map(async asset => {
      let css = await (await loadAsset(asset)).text();
      const references = [...css.matchAll(/url\(\s*(["']?)(.*?)\1\s*\)/gi)];
      for (const match of references) {
        const url = new URL(match[2], asset.url).href;
        if (!url.startsWith(cdn.fonts) || !/\.(?:woff2?|ttf)$/.test(url)) continue;
        const data = await asDataURL(await loadAsset({ url }));
        css = css.replaceAll(match[0], "url(" + JSON.stringify(data) + ")");
      }
      return "<style>" + css.replace(/<\/style/gi, "<\\/style") + "</style>";
    }));
  }

  // Keep automatic rendering and the page's own Mermaid calls in one queue.
  function prepareMermaid() {
    const mermaid = window.mermaid;
    const initialize = mermaid.initialize.bind(mermaid);
    mermaid.initialize = config => initialize({
      ...config, startOnLoad: false, securityLevel: "strict", maxTextSize: 50000,
      maxEdges: 500, suppressErrorRendering: true,
      secure: ["secure", "securityLevel", "startOnLoad", "maxTextSize", "maxEdges",
        "suppressErrorRendering", "dompurifyConfig", "themeCSS"]
    });
    mermaid.initialize({ startOnLoad: false });
    const run = mermaid.run.bind(mermaid);
    let queue = Promise.resolve();
    mermaid.run = options => {
      queue = queue.catch(() => {}).then(() => run(options));
      window.previewMermaidReady = queue;
      return queue;
    };
  }

  async function buildPreview(html, scriptsEnabled, version) {
    const input = document.createElement("template");
    input.innerHTML = html;
    const output = document.createElement("template");
    const styles = new Map();
    const fonts = new Map();
    // Iterative traversal also handles deeply nested pasted markup.
    const pending = [[input.content, output.content]];
    while (pending.length) {
      const [from, to] = pending.pop();
      for (const node of from.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) {
          to.appendChild(document.createTextNode(node.textContent));
          continue;
        }
        if (node.nodeType !== Node.ELEMENT_NODE ||
            node.namespaceURI !== "http://www.w3.org/1999/xhtml") {
          continue;
        }
        if (node.localName === "link" && node.relList.contains("stylesheet")) {
          const asset = cdn.styles.find(entry => entry.url === node.getAttribute("href"));
          if (asset) styles.set(asset.url, asset);
          try {
            const url = new URL(node.getAttribute("href"));
            if (url.origin === "https://fonts.googleapis.com" && url.pathname === "/css2") {
              for (const family of url.searchParams.getAll("family")) {
                const font = cdn.webfonts.find(entry => entry.name === family.split(":")[0]);
                if (font) fonts.set(font.name, font);
              }
            }
          } catch (_) { /* Only absolute supported font links are recognized. */ }
          continue;
        }
        if (scriptsEnabled && node.localName === "script" && !node.hasAttribute("src") &&
            (!node.type || /^(?:text|application)\/javascript$/i.test(node.type))) {
          const script = document.createElement("script");
          script.textContent = node.textContent.replace(/<\/script/gi, "<\\/script");
          to.appendChild(script);
          // Adoption into the inert template clears a nonce set beforehand.
          script.setAttribute("nonce", nonce);
          continue;
        }
        if (!allowedTags.has(node.localName)) continue;
        const clean = document.createElement(node.localName);
        for (const attribute of node.attributes) {
          if (allowedAttributes.has(attribute.name) || (scriptsEnabled &&
              (/^(?:data-|aria-)/.test(attribute.name) ||
                ["for", "role", "tabindex", "name"].includes(attribute.name)))) {
            clean.setAttribute(attribute.name, attribute.value);
          }
        }
        if (node.localName === "img" && rasterData.test(node.getAttribute("src") || "")) {
          clean.setAttribute("src", node.getAttribute("src"));
        }
        if (node.localName === "a" && node.getAttribute("href")?.startsWith("#")) {
          try {
            clean.dataset.previewTarget = decodeURIComponent(node.getAttribute("href").slice(1));
            clean.setAttribute("role", "link");
            clean.setAttribute("tabindex", "0");
            if (scriptsEnabled) clean.setAttribute("href", node.getAttribute("href"));
          } catch (_) {
            // Malformed fragments remain inert, like external links.
          }
        }
        if (!scriptsEnabled && controls.has(node.localName)) clean.setAttribute("disabled", "");
        to.appendChild(clean);
        pending.push([node, clean]);
      }
    }
    const styleSources = cdn.styles.map(asset => asset.url).join(" ");
    const policy = scriptsEnabled
      ? "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; " +
        "font-src data:; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'"
      : "default-src 'none'; script-src 'nonce-" + nonce + "'; " +
        "style-src 'unsafe-inline'; font-src data: " + cdn.fonts + "; " +
        "img-src data:; connect-src " + styleSources + "; base-uri 'none'; form-action 'none'";
    let preloadFailed = false;
    const unavailable = () => { preloadFailed = true; return ""; };
    let prepared = (await Promise.all([...fonts.values()].map(async asset => {
      const data = await asDataURL(await loadAsset(asset));
      return "<style>@font-face{font-family:" + JSON.stringify(asset.name) +
        ";font-style:normal;font-weight:100 900;font-display:swap;src:url(" +
        JSON.stringify(data) + ") format('truetype')}</style>";
    }).map(request => request.catch(unavailable)))).join("");
    if (scriptsEnabled) {
      prepared += await prepareStyles([...styles.values()]).then(styles => styles.join(""), unavailable);
      if (output.content.querySelector("pre.mermaid, div.mermaid")) {
        try {
          prepared += inlineScript(await (await loadAsset(cdn.mermaid)).text());
          prepared += inlineScript("(" + prepareMermaid.toString() + ")();");
        } catch (_) {
          unavailable();
        }
      }
    }
    const renderer = "(" + renderFrame.toString() + ")(" +
      JSON.stringify(scriptsEnabled ? [] : [...styles.values()]) + "," + JSON.stringify(cdn.mermaid) + "," + version + "," + scriptsEnabled + "," + preloadFailed + ");";
    return "<!doctype html><html><head><meta charset='utf-8'>" +
      "<meta http-equiv='Content-Security-Policy' content=\"" + policy + "\">" +
      "<meta name='referrer' content='no-referrer'>" +
      "<meta name='viewport' content='width=device-width, initial-scale=1'>" +
      "<style>body{margin:20px;font-family:system-ui,sans-serif;line-height:1.6;" +
      "overflow-wrap:anywhere}img{max-width:100%;height:auto}pre{overflow:auto}" +
      "table{max-width:100%}.mermaid{max-width:100%;overflow:auto}</style>" + prepared + "</head><body>" +
      output.innerHTML + inlineScript(renderer) + "</body></html>";
  }

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
        const html = await buildPreview(source.value, executeScripts.checked, version);
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
