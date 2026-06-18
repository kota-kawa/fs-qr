/*!
 * FS!QR Global UX Runtime
 * -----------------------------------------------------------------------------
 * Progressive-enhancement layer applied on every page through the shared
 * layouts. Adds a modern, interactive feel and resilience on slow / flaky
 * networks *without changing the existing design*:
 *
 *   - Top navigation progress bar (perceived speed on slow links)
 *   - Connection-aware link prefetch (hover / touch / focus / in-viewport)
 *   - Lightweight non-blocking toasts
 *   - Online / offline awareness with subtle banner + events
 *   - Subtle micro-interactions (ripple, press feedback, smooth anchor scroll)
 *
 * Everything degrades gracefully and honours `prefers-reduced-motion` and the
 * Save-Data / slow-connection signals. No external dependencies.
 *
 * Public API: window.FSQRUx
 *   FSQRUx.progress.start() / .done() / .set(0..1)
 *   FSQRUx.toast(message, { type, duration })
 *   FSQRUx.isOnline()
 *   FSQRUx.connection  -> { saveData, slow, effectiveType }
 */
(function (window, document) {
  "use strict";

  if (window.FSQRUx) {
    return;
  }

  var docEl = document.documentElement;

  // ---------------------------------------------------------------------------
  // Environment / capability detection
  // ---------------------------------------------------------------------------
  var prefersReducedMotion = false;
  try {
    prefersReducedMotion =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-reduced-motion: reduce)");
      var onMqChange = function (event) {
        prefersReducedMotion = event.matches;
      };
      if (typeof mq.addEventListener === "function") {
        mq.addEventListener("change", onMqChange);
      } else if (typeof mq.addListener === "function") {
        mq.addListener(onMqChange);
      }
    }
  } catch (err) {
    prefersReducedMotion = false;
  }

  function readConnection() {
    var info = { saveData: false, slow: false, effectiveType: "" };
    try {
      var conn =
        navigator.connection ||
        navigator.mozConnection ||
        navigator.webkitConnection;
      if (conn) {
        info.saveData = Boolean(conn.saveData);
        info.effectiveType = conn.effectiveType || "";
        info.slow =
          info.effectiveType === "slow-2g" || info.effectiveType === "2g";
      }
    } catch (err) {
      /* noop */
    }
    return info;
  }

  var connection = readConnection();
  try {
    var liveConn =
      navigator.connection ||
      navigator.mozConnection ||
      navigator.webkitConnection;
    if (liveConn && typeof liveConn.addEventListener === "function") {
      liveConn.addEventListener("change", function () {
        connection = readConnection();
      });
    }
  } catch (err) {
    /* noop */
  }

  function isSameOrigin(url) {
    try {
      var parsed = new URL(url, window.location.href);
      return parsed.origin === window.location.origin;
    } catch (err) {
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Top progress bar
  // ---------------------------------------------------------------------------
  var progress = (function () {
    var bar = null;
    var visible = false;
    var current = 0;
    var trickleTimer = null;
    var doneTimer = null;

    function ensureBar() {
      if (bar) {
        return bar;
      }
      bar = document.createElement("div");
      bar.className = "fsqr-progress";
      bar.setAttribute("role", "progressbar");
      bar.setAttribute("aria-hidden", "true");
      var inner = document.createElement("div");
      inner.className = "fsqr-progress__bar";
      bar.appendChild(inner);
      (document.body || docEl).appendChild(bar);
      return bar;
    }

    function render() {
      var node = ensureBar();
      var inner = node.firstChild;
      var pct = Math.max(0, Math.min(1, current));
      inner.style.transform = "scaleX(" + pct + ")";
    }

    function clearTimers() {
      if (trickleTimer) {
        window.clearInterval(trickleTimer);
        trickleTimer = null;
      }
      if (doneTimer) {
        window.clearTimeout(doneTimer);
        doneTimer = null;
      }
    }

    function start() {
      clearTimers();
      var node = ensureBar();
      visible = true;
      current = current > 0 && current < 0.95 ? current : 0.08;
      node.classList.add("is-active");
      node.classList.remove("is-done");
      render();
      trickleTimer = window.setInterval(function () {
        // Ease towards 0.9 but never reach it until done() is called.
        var remaining = 0.9 - current;
        if (remaining <= 0.001) {
          return;
        }
        current += remaining * 0.08 + 0.004;
        render();
      }, 300);
    }

    function set(value) {
      if (!visible) {
        start();
      }
      current = Math.max(current, Math.min(0.95, value));
      render();
    }

    function done() {
      if (!visible) {
        return;
      }
      clearTimers();
      visible = false;
      current = 1;
      render();
      var node = ensureBar();
      node.classList.add("is-done");
      doneTimer = window.setTimeout(function () {
        node.classList.remove("is-active");
        node.classList.remove("is-done");
        current = 0;
        render();
      }, 280);
    }

    return { start: start, set: set, done: done };
  })();

  // ---------------------------------------------------------------------------
  // Toasts
  // ---------------------------------------------------------------------------
  var toast = (function () {
    var container = null;

    function ensureContainer() {
      if (container && document.body.contains(container)) {
        return container;
      }
      container = document.createElement("div");
      container.className = "fsqr-toast-stack";
      container.setAttribute("aria-live", "polite");
      container.setAttribute("aria-atomic", "false");
      (document.body || docEl).appendChild(container);
      return container;
    }

    function show(message, options) {
      if (!message) {
        return null;
      }
      options = options || {};
      var type = options.type || "info";
      var duration =
        typeof options.duration === "number" ? options.duration : 3600;

      var node = document.createElement("div");
      node.className = "fsqr-toast fsqr-toast--" + type;
      node.setAttribute("role", type === "error" ? "alert" : "status");
      node.textContent = message;
      ensureContainer().appendChild(node);

      // Force reflow so the entry transition runs.
      // eslint-disable-next-line no-unused-expressions
      node.offsetHeight;
      node.classList.add("is-visible");

      var hideTimer = null;
      function dismiss() {
        if (hideTimer) {
          window.clearTimeout(hideTimer);
          hideTimer = null;
        }
        node.classList.remove("is-visible");
        window.setTimeout(function () {
          if (node.parentNode) {
            node.parentNode.removeChild(node);
          }
        }, 260);
      }

      node.addEventListener("click", dismiss);
      if (duration > 0) {
        hideTimer = window.setTimeout(dismiss, duration);
      }
      return { dismiss: dismiss, node: node };
    }

    return show;
  })();

  // ---------------------------------------------------------------------------
  // i18n helper (uses page-provided translations when available)
  // ---------------------------------------------------------------------------
  function t(key, fallback) {
    try {
      if (window.FSQR_I18N && typeof window.FSQR_I18N.t === "function") {
        return window.FSQR_I18N.t(key, fallback);
      }
    } catch (err) {
      /* noop */
    }
    return fallback;
  }

  // ---------------------------------------------------------------------------
  // Online / offline awareness
  // ---------------------------------------------------------------------------
  var net = (function () {
    var banner = null;
    var lastOnline = navigator.onLine !== false;

    function ensureBanner() {
      if (banner) {
        return banner;
      }
      banner = document.createElement("div");
      banner.className = "fsqr-offline-banner";
      banner.setAttribute("role", "status");
      banner.setAttribute("aria-live", "polite");
      banner.hidden = true;
      (document.body || docEl).appendChild(banner);
      return banner;
    }

    function showBanner(text) {
      var node = ensureBanner();
      node.textContent = text;
      node.hidden = false;
      // reflow for transition
      // eslint-disable-next-line no-unused-expressions
      node.offsetHeight;
      node.classList.add("is-visible");
    }

    function hideBanner() {
      if (!banner) {
        return;
      }
      banner.classList.remove("is-visible");
      window.setTimeout(function () {
        if (banner) {
          banner.hidden = true;
        }
      }, 300);
    }

    function handleOffline() {
      if (lastOnline === false) {
        return;
      }
      lastOnline = false;
      showBanner(t("net.offline", "オフラインです。接続を確認しています…"));
      try {
        document.dispatchEvent(new CustomEvent("fsqr:offline"));
      } catch (err) {
        /* noop */
      }
    }

    function handleOnline() {
      if (lastOnline === true) {
        return;
      }
      lastOnline = true;
      hideBanner();
      toast(t("net.online", "再接続しました"), { type: "success" });
      try {
        document.dispatchEvent(new CustomEvent("fsqr:online"));
      } catch (err) {
        /* noop */
      }
    }

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    // Reflect the initial state (e.g. page loaded while offline).
    if (navigator.onLine === false) {
      lastOnline = true; // force handleOffline to run once
      handleOffline();
    }

    return {
      isOnline: function () {
        return lastOnline;
      },
    };
  })();

  // ---------------------------------------------------------------------------
  // Navigation progress hooks (full page loads)
  // ---------------------------------------------------------------------------
  (function navigationProgress() {
    var watchdog = null;
    var unloading = false;

    function clearWatchdog() {
      if (watchdog) {
        window.clearTimeout(watchdog);
        watchdog = null;
      }
    }

    function shouldTrack(anchor, event) {
      // Runs in the bubble phase: if the page intercepted the click
      // (e.g. an async / SPA-style handler), defaultPrevented is already set
      // and we must not show the bar.
      if (!anchor || event.defaultPrevented) {
        return false;
      }
      if (event.button !== 0 || event.metaKey || event.ctrlKey ||
          event.shiftKey || event.altKey) {
        return false;
      }
      var href = anchor.getAttribute("href");
      if (!href || href.charAt(0) === "#") {
        return false;
      }
      if (anchor.target && anchor.target !== "_self") {
        return false;
      }
      if (anchor.hasAttribute("download") ||
          anchor.hasAttribute("data-no-progress")) {
        return false;
      }
      var proto = (anchor.protocol || "").toLowerCase();
      if (proto === "mailto:" || proto === "tel:" || proto === "blob:" ||
          proto === "javascript:") {
        return false;
      }
      if (!isSameOrigin(anchor.href)) {
        return false;
      }
      // Same page (hash only) navigation -> no progress.
      if (anchor.href.split("#")[0] === window.location.href.split("#")[0]) {
        return false;
      }
      return true;
    }

    // Bubble phase so page handlers run first and we can read defaultPrevented.
    document.addEventListener("click", function (event) {
      var anchor = event.target.closest
        ? event.target.closest("a[href]")
        : null;
      if (!shouldTrack(anchor, event)) {
        return;
      }
      progress.start();
      // If a real navigation happens, `beforeunload` fires and cancels this.
      // Otherwise (intercepted later / blocked) auto-clear so it never sticks.
      clearWatchdog();
      watchdog = window.setTimeout(function () {
        if (!unloading) {
          progress.done();
        }
      }, 1500);
    });

    // The reliable signal that the document is actually navigating away.
    window.addEventListener("beforeunload", function () {
      unloading = true;
      clearWatchdog();
      progress.start();
    });

    // bfcache restores / aborted navigations -> clear the bar.
    window.addEventListener("pageshow", function () {
      unloading = false;
      clearWatchdog();
      progress.done();
    });
  })();

  // ---------------------------------------------------------------------------
  // Link prefetch (connection-aware)
  // ---------------------------------------------------------------------------
  (function prefetch() {
    if (connection.saveData || connection.slow) {
      return;
    }
    var supportsPrefetch = (function () {
      try {
        var link = document.createElement("link");
        return link.relList && link.relList.supports
          ? link.relList.supports("prefetch")
          : true;
      } catch (err) {
        return false;
      }
    })();
    if (!supportsPrefetch) {
      return;
    }

    var prefetched = Object.create(null);
    var inFlight = 0;
    var MAX_IN_FLIGHT = 2;

    function eligible(anchor) {
      if (!anchor) {
        return false;
      }
      var href = anchor.getAttribute("href");
      if (!href || href.charAt(0) === "#") {
        return false;
      }
      if (anchor.target && anchor.target !== "_self") {
        return false;
      }
      if (anchor.hasAttribute("download") ||
          anchor.hasAttribute("data-no-prefetch")) {
        return false;
      }
      var url = anchor.href;
      if (!isSameOrigin(url)) {
        return false;
      }
      var clean = url.split("#")[0];
      if (clean === window.location.href.split("#")[0]) {
        return false;
      }
      if (prefetched[clean]) {
        return false;
      }
      var proto = (anchor.protocol || "").toLowerCase();
      if (proto !== "http:" && proto !== "https:") {
        return false;
      }
      return true;
    }

    function doPrefetch(anchor) {
      if (!eligible(anchor) || inFlight >= MAX_IN_FLIGHT) {
        return;
      }
      var clean = anchor.href.split("#")[0];
      prefetched[clean] = true;
      inFlight += 1;
      var link = document.createElement("link");
      link.rel = "prefetch";
      link.href = clean;
      link.as = "document";
      var release = function () {
        inFlight = Math.max(0, inFlight - 1);
      };
      link.addEventListener("load", release);
      link.addEventListener("error", release);
      document.head.appendChild(link);
      // Safety release in case events never fire.
      window.setTimeout(release, 8000);
    }

    var hoverTimer = null;
    function onIntent(event) {
      var anchor = event.target.closest
        ? event.target.closest("a[href]")
        : null;
      if (!anchor) {
        return;
      }
      if (event.type === "mouseover") {
        if (hoverTimer) {
          window.clearTimeout(hoverTimer);
        }
        hoverTimer = window.setTimeout(function () {
          doPrefetch(anchor);
        }, 65);
      } else {
        doPrefetch(anchor);
      }
    }
    function cancelHover() {
      if (hoverTimer) {
        window.clearTimeout(hoverTimer);
        hoverTimer = null;
      }
    }

    document.addEventListener("mouseover", onIntent, { passive: true });
    document.addEventListener("mouseout", cancelHover, { passive: true });
    document.addEventListener("focusin", onIntent, { passive: true });
    document.addEventListener("touchstart", onIntent, { passive: true });

    // Idle prefetch of in-viewport links (gentle, capped).
    if ("IntersectionObserver" in window && "requestIdleCallback" in window) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              var anchor = entry.target;
              observer.unobserve(anchor);
              window.requestIdleCallback(function () {
                doPrefetch(anchor);
              });
            }
          });
        },
        { rootMargin: "200px" }
      );
      window.requestIdleCallback(function () {
        var anchors = document.querySelectorAll("a[href]");
        var count = 0;
        for (var i = 0; i < anchors.length && count < 12; i += 1) {
          if (eligible(anchors[i])) {
            observer.observe(anchors[i]);
            count += 1;
          }
        }
      });
    }
  })();

  // ---------------------------------------------------------------------------
  // Micro-interactions: ripple + press feedback + smooth anchor scroll
  // ---------------------------------------------------------------------------
  (function microInteractions() {
    docEl.classList.add("fsqr-ux-ready");

    var RIPPLE_SELECTOR =
      "button, .btn, [role='button'], .section-tab, .footer-link-button";

    if (!prefersReducedMotion) {
      document.addEventListener(
        "pointerdown",
        function (event) {
          if (event.pointerType === "mouse" && event.button !== 0) {
            return;
          }
          var target = event.target.closest
            ? event.target.closest(RIPPLE_SELECTOR)
            : null;
          if (!target || target.disabled) {
            return;
          }
          if (target.hasAttribute("data-no-ripple")) {
            return;
          }
          var rect = target.getBoundingClientRect();
          if (!rect.width || !rect.height) {
            return;
          }
          var ripple = document.createElement("span");
          ripple.className = "fsqr-ripple";
          var size = Math.max(rect.width, rect.height);
          ripple.style.width = ripple.style.height = size + "px";
          ripple.style.left = event.clientX - rect.left - size / 2 + "px";
          ripple.style.top = event.clientY - rect.top - size / 2 + "px";

          // Apply clipping / positioning only for the duration of the ripple,
          // then restore so the control's resting styles are untouched.
          var cs = window.getComputedStyle(target);
          var addedHost = false;
          var addedClip = false;
          if (cs.position === "static") {
            target.classList.add("fsqr-ripple-host");
            addedHost = true;
          }
          if (cs.overflow !== "hidden") {
            target.classList.add("fsqr-ripple-clip");
            addedClip = true;
          }
          target.setAttribute(
            "data-fsqr-ripples",
            String((parseInt(target.getAttribute("data-fsqr-ripples"), 10) || 0) + 1)
          );
          target.appendChild(ripple);
          ripple.addEventListener("animationend", function () {
            if (ripple.parentNode) {
              ripple.parentNode.removeChild(ripple);
            }
            var remaining =
              (parseInt(target.getAttribute("data-fsqr-ripples"), 10) || 1) - 1;
            if (remaining <= 0) {
              target.removeAttribute("data-fsqr-ripples");
              if (addedHost) {
                target.classList.remove("fsqr-ripple-host");
              }
              if (addedClip) {
                target.classList.remove("fsqr-ripple-clip");
              }
            } else {
              target.setAttribute("data-fsqr-ripples", String(remaining));
            }
          });
        },
        { passive: true }
      );
    }

    // Smooth scroll for in-page anchors (honours reduced-motion).
    document.addEventListener("click", function (event) {
      var anchor = event.target.closest
        ? event.target.closest('a[href^="#"]')
        : null;
      if (!anchor) {
        return;
      }
      var id = anchor.getAttribute("href");
      if (!id || id === "#") {
        return;
      }
      var target;
      try {
        target = document.querySelector(id);
      } catch (err) {
        return;
      }
      if (!target) {
        return;
      }
      event.preventDefault();
      target.scrollIntoView({
        behavior: prefersReducedMotion ? "auto" : "smooth",
        block: "start",
      });
      if (typeof target.focus === "function") {
        target.setAttribute("tabindex", "-1");
        target.focus({ preventScroll: true });
      }
    });
  })();

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------
  window.FSQRUx = Object.freeze({
    progress: progress,
    toast: toast,
    isOnline: net.isOnline,
    get connection() {
      return connection;
    },
    prefersReducedMotion: function () {
      return prefersReducedMotion;
    },
  });

  // Register in the shared namespace too, when present.
  try {
    var ns = window.__FSQR_APP__;
    if (ns && ns.api && typeof ns.api.setShared === "function") {
      ns.api.setShared("ux", window.FSQRUx);
    }
  } catch (err) {
    /* noop */
  }
})(window, document);
