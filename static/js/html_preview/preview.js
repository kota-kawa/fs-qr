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
  let renderVersion = 0;

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

  // Only this service-owned renderer and the pinned Mermaid bundle execute
  // inside the opaque sandbox. No pasted script or event handler survives.
  async function renderFrame(styles, mermaidAsset, version) {
    const rendererNonce = document.currentScript.nonce;
    const report = (state) => parent.postMessage({
      type: "html-preview", state, version,
      height: document.documentElement.scrollHeight
    }, "*");
    let failed = false;
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
    failed = stylesReady.some(result => result.status === "rejected");
    const diagrams = document.querySelectorAll("pre.mermaid, div.mermaid");
    if (diagrams.length) {
      try {
        await new Promise((resolve, reject) => {
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
        mermaid.initialize({
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
        await mermaid.run({ nodes: diagrams });
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
  }

  function buildPreview(html) {
    const input = document.createElement("template");
    input.innerHTML = html;
    const output = document.createElement("template");
    const styles = new Map();
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
          continue;
        }
        if (!allowedTags.has(node.localName)) continue;
        const clean = document.createElement(node.localName);
        for (const attribute of node.attributes) {
          if (allowedAttributes.has(attribute.name)) {
            clean.setAttribute(attribute.name, attribute.value);
          }
        }
        if (node.localName === "img" && rasterData.test(node.getAttribute("src") || "")) {
          clean.setAttribute("src", node.getAttribute("src"));
        }
        if (controls.has(node.localName)) clean.setAttribute("disabled", "");
        to.appendChild(clean);
        pending.push([node, clean]);
      }
    }
    const styleSources = cdn.styles.map(asset => asset.url).join(" ");
    const policy = "default-src 'none'; script-src 'nonce-" + nonce + "'; " +
      "style-src 'unsafe-inline'; font-src " + cdn.fonts + "; " +
      "img-src data:; connect-src " + styleSources + "; base-uri 'none'; form-action 'none'";
    const renderer = "(" + renderFrame.toString() + ")(" +
      JSON.stringify([...styles.values()]) + "," + JSON.stringify(cdn.mermaid) + "," + renderVersion + ");";
    return "<!doctype html><html><head><meta charset='utf-8'>" +
      "<meta http-equiv='Content-Security-Policy' content=\"" + policy + "\">" +
      "<meta name='referrer' content='no-referrer'>" +
      "<meta name='viewport' content='width=device-width, initial-scale=1'>" +
      "<style>body{margin:20px;font-family:system-ui,sans-serif;line-height:1.6;" +
      "overflow-wrap:anywhere}img{max-width:100%;height:auto}pre{overflow:auto}" +
      "table{max-width:100%}.mermaid{max-width:100%;overflow:auto}</style></head><body>" +
      output.innerHTML + "<script nonce='" + nonce + "'>" + renderer + "</script></body></html>";
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
  document.getElementById("render-preview").addEventListener("click", function () {
    try {
      renderVersion += 1;
      frame.style.height = "";
      if (!source.value.trim()) {
        frame.removeAttribute("srcdoc");
        frame.hidden = true;
        empty.hidden = false;
        status.textContent = "";
      } else {
        frame.srcdoc = buildPreview(source.value);
        frame.hidden = false;
        empty.hidden = true;
        status.textContent = status.dataset.loading;
      }
      showView("preview", true);
    } catch (_) {
      status.textContent = status.dataset.error;
      showView("preview", true);
    }
  });
})();
