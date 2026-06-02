/**
 * ページ単位の「現在の閲覧者数」を表示するウィジェット。
 *
 * data-presence-scope / data-presence-key を持つ要素を探し、
 * 一定間隔でハートビートを送りつつ最新の閲覧者数を表示する。
 * ブラウザを閉じる/離脱する際は sendBeacon で離脱を通知する。
 */
(function () {
  "use strict";

  var HEARTBEAT_INTERVAL_MS = 10000;
  var STORAGE_KEY = "fsqr_presence_viewer_id";

  function t(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === "function") {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback;
  }

  function viewerId() {
    var id = null;
    try {
      id = window.sessionStorage.getItem(STORAGE_KEY);
    } catch (e) {
      id = null;
    }
    if (!id) {
      id = "v-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      try {
        window.sessionStorage.setItem(STORAGE_KEY, id);
      } catch (e) {
        /* sessionStorage が使えなくてもこのセッション中は id を使い回す */
      }
    }
    return id;
  }

  function formatLabel(count) {
    var template = t("presence.viewers", "現在 {count} 人が閲覧中");
    if (template.indexOf("{count}") !== -1) {
      return template.replace("{count}", count);
    }
    return template + " " + count;
  }

  function setupWidget(el) {
    var scope = el.getAttribute("data-presence-scope");
    var key = el.getAttribute("data-presence-key");
    if (!scope || !key) {
      return;
    }

    var vid = viewerId();
    var base =
      "/api/presence/" +
      encodeURIComponent(scope) +
      "/" +
      encodeURIComponent(key);
    var labelEl = el.querySelector(".fsqr-presence__label");
    var timer = null;

    function render(count) {
      if (typeof count !== "number" || count < 0) {
        return;
      }
      if (labelEl) {
        labelEl.textContent = formatLabel(count);
      }
      el.hidden = false;
    }

    function heartbeat() {
      var url = base + "?viewer_id=" + encodeURIComponent(vid);
      fetch(url, {
        method: "POST",
        headers: { Accept: "application/json" },
        keepalive: true,
      })
        .then(function (res) {
          return res.ok ? res.json() : null;
        })
        .then(function (payload) {
          if (payload && payload.data && typeof payload.data.count === "number") {
            render(payload.data.count);
          }
        })
        .catch(function () {
          /* 一時的な失敗は無視し、次回のハートビートで回復させる */
        });
    }

    function leave() {
      var url = base + "/leave?viewer_id=" + encodeURIComponent(vid);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(url);
      } else {
        fetch(url, { method: "POST", keepalive: true }).catch(function () {});
      }
    }

    heartbeat();
    timer = window.setInterval(heartbeat, HEARTBEAT_INTERVAL_MS);

    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") {
        heartbeat();
      }
    });

    window.addEventListener("pagehide", function () {
      if (timer) {
        window.clearInterval(timer);
        timer = null;
      }
      leave();
    });
  }

  function init() {
    var widgets = document.querySelectorAll("[data-presence-scope]");
    for (var i = 0; i < widgets.length; i++) {
      setupWidget(widgets[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
