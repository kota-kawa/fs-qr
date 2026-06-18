/*!
 * FS!QR Service Worker registration
 * -----------------------------------------------------------------------------
 * Registers /sw.js (root scope) so it can cache static assets and provide an
 * offline fallback for navigations. Surfaces a gentle toast when an updated
 * worker is ready. No-ops on unsupported browsers or insecure origins.
 */
(function (window, navigator) {
  "use strict";

  if (!("serviceWorker" in navigator)) {
    return;
  }

  // Service workers require a secure context (https) or localhost.
  if (
    !window.isSecureContext &&
    location.hostname !== "localhost" &&
    location.hostname !== "127.0.0.1"
  ) {
    return;
  }

  function notifyUpdate(worker) {
    function reloadOnce() {
      if (window.__fsqrReloadingForSw) {
        return;
      }
      window.__fsqrReloadingForSw = true;
      window.location.reload();
    }

    var message = "新しいバージョンがあります。タップして更新";
    try {
      if (window.FSQR_I18N && typeof window.FSQR_I18N.t === "function") {
        message = window.FSQR_I18N.t("sw.update", message);
      }
    } catch (err) {
      /* noop */
    }

    if (window.FSQRUx && typeof window.FSQRUx.toast === "function") {
      var handle = window.FSQRUx.toast(message, {
        type: "info",
        duration: 12000,
      });
      if (handle && handle.node) {
        handle.node.addEventListener("click", function () {
          worker.postMessage("fsqr-skip-waiting");
        });
      }
    }

    // When the new worker takes control, reload to pick up fresh assets.
    navigator.serviceWorker.addEventListener("controllerchange", reloadOnce);
  }

  window.addEventListener("load", function () {
    navigator.serviceWorker
      .register("/sw.js")
      .then(function (registration) {
        registration.addEventListener("updatefound", function () {
          var installing = registration.installing;
          if (!installing) {
            return;
          }
          installing.addEventListener("statechange", function () {
            // A new worker is installed and waiting while an old one controls
            // the page -> offer to update. (First install has no controller.)
            if (
              installing.state === "installed" &&
              navigator.serviceWorker.controller
            ) {
              notifyUpdate(installing);
            }
          });
        });
      })
      .catch(function () {
        /* Registration failures are non-fatal. */
      });
  });
})(window, navigator);
