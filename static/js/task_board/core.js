(function (window) {
  'use strict';
  var app = window.__FSQR_APP__;
  if (!app || !app.api) { throw new Error('App namespace is not initialized.'); }
  var modules = app.api.getModuleNamespace('taskBoard');
  function t(key, fallback) { return window.FSQR_I18N && window.FSQR_I18N.t ? window.FSQR_I18N.t(key, fallback) : (fallback || key); }
  function csrf() { var meta = document.querySelector('meta[name="csrf-token"]'); return meta ? meta.content : ''; }
  function toast(message, type) { if (window.FSQRUx && window.FSQRUx.toast) { window.FSQRUx.toast(message, { type: type || 'info' }); } }
  async function request(path, options) {
    var controller = new AbortController();
    var timeout = window.setTimeout(function () { controller.abort(); }, 15000);
    try {
      var opts = Object.assign({ credentials: 'same-origin', signal: controller.signal, headers: {} }, options || {});
      opts.headers = Object.assign({ Accept: 'application/json' }, opts.headers);
      if (opts.method && opts.method !== 'GET') { opts.headers['X-CSRF-Token'] = csrf(); opts.headers['Content-Type'] = 'application/json'; }
      var response = await fetch(path, opts);
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok || payload.status !== 'ok') { var error = new Error(payload.error || '通信に失敗しました。'); error.status = response.status; error.data = payload.data; throw error; }
      return payload.data;
    } finally { window.clearTimeout(timeout); }
  }
  modules.core = { config: app.api.getConfig('taskBoard'), t: t, csrf: csrf, toast: toast, request: request };
})(window);
