/*!
 * FS!QR Service Worker
 * -----------------------------------------------------------------------------
 * Goal: make the service resilient on slow / flaky networks WITHOUT ever
 * serving stale dynamic content.
 *
 * Strategy:
 *   - Static assets under /static/*  -> stale-while-revalidate
 *     (instant from cache, refreshed in the background). These are already
 *     cache-busted with a ?v=<mtime> query, so a changed file is a new URL.
 *   - HTML navigations               -> network-only, with a minimal offline
 *     fallback page shown only when the network is unavailable.
 *   - Everything else (APIs, non-GET, cross-origin, websockets) -> untouched.
 *
 * Bump CACHE_VERSION to invalidate all previously cached static assets.
 */
"use strict";

var CACHE_VERSION = "v1";
var STATIC_CACHE = "fsqr-static-" + CACHE_VERSION;

var OFFLINE_HTML =
  "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
  "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" +
  "<title>オフライン | FS!QR</title><style>" +
  "body{margin:0;min-height:100vh;display:flex;align-items:center;" +
  "justify-content:center;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;" +
  "background:#f8fafc;color:#1f2937;padding:1.5rem;text-align:center}" +
  ".card{max-width:24rem}h1{font-size:1.3rem;margin:0 0 .5rem}" +
  "p{color:#6b7280;line-height:1.6;margin:0 0 1.25rem}" +
  "button{font:inherit;padding:.6rem 1.4rem;border:0;border-radius:999px;" +
  "color:#fff;background:linear-gradient(135deg,#23c3df,#1f27c7);cursor:pointer}" +
  "</style></head><body><div class=\"card\"><h1>オフラインです</h1>" +
  "<p>インターネットに接続できませんでした。接続を確認してからもう一度お試しください。</p>" +
  "<button onclick=\"location.reload()\">再読み込み</button></div></body></html>";

function isStaticAsset(url) {
  return url.origin === self.location.origin &&
    url.pathname.indexOf("/static/") === 0;
}

self.addEventListener("install", function (event) {
  // Activate the new worker as soon as it has installed.
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        return Promise.all(
          keys.map(function (key) {
            if (key !== STATIC_CACHE && key.indexOf("fsqr-static-") === 0) {
              return caches.delete(key);
            }
            return undefined;
          })
        );
      })
      .then(function () {
        return self.clients.claim();
      })
  );
});

function staleWhileRevalidate(request) {
  return caches.open(STATIC_CACHE).then(function (cache) {
    return cache.match(request).then(function (cached) {
      var network = fetch(request)
        .then(function (response) {
          if (response && response.ok && response.type === "basic") {
            cache.put(request, response.clone());
          }
          return response;
        })
        .catch(function () {
          return cached;
        });
      // Serve cache immediately when present; otherwise wait for network.
      return cached || network;
    });
  });
}

self.addEventListener("fetch", function (event) {
  var request = event.request;

  // Only ever handle GET; leave uploads, websockets, APIs untouched.
  if (request.method !== "GET") {
    return;
  }

  var url;
  try {
    url = new URL(request.url);
  } catch (err) {
    return;
  }

  // Static assets: stale-while-revalidate.
  if (isStaticAsset(url)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // HTML navigations: network-only with an offline fallback.
  if (
    request.mode === "navigate" ||
    (request.headers.get("accept") || "").indexOf("text/html") !== -1
  ) {
    // Same-origin only; cross-origin navigations are left to the browser.
    if (url.origin !== self.location.origin) {
      return;
    }
    event.respondWith(
      fetch(request).catch(function () {
        return new Response(OFFLINE_HTML, {
          status: 503,
          headers: { "Content-Type": "text/html; charset=utf-8" },
        });
      })
    );
    return;
  }

  // Everything else: do not intercept (default browser behaviour).
});

// Allow the page to trigger an immediate update when a new worker is waiting.
self.addEventListener("message", function (event) {
  if (event.data === "fsqr-skip-waiting") {
    self.skipWaiting();
  }
});
