(function (window) {
  'use strict';

  var app = window.__FSQR_APP__;
  if (!app || !app.api) {
    throw new Error('App namespace is not initialized.');
  }

  var modules = app.api.getModuleNamespace('taskBoard');

  function t(key, fallback) {
    return window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function'
      ? window.FSQR_I18N.t(key, fallback)
      : (fallback || key);
  }

  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  function toast(message, type) {
    if (window.FSQRUx && typeof window.FSQRUx.toast === 'function') {
      window.FSQRUx.toast(message, { type: type || 'info' });
    }
  }

  async function request(path, options) {
    var controller = new AbortController();
    var timeout = window.setTimeout(function () {
      controller.abort();
    }, 15000);

    try {
      var opts = Object.assign(
        { credentials: 'same-origin', signal: controller.signal, headers: {} },
        options || {}
      );
      opts.headers = Object.assign({ Accept: 'application/json' }, opts.headers);

      if (opts.method && opts.method !== 'GET') {
        opts.headers['X-CSRF-Token'] = csrf();
        opts.headers['Content-Type'] = 'application/json';
      }

      var response = await fetch(path, opts);
      var payload = await response.json().catch(function () {
        return {};
      });

      if (!response.ok || payload.status !== 'ok') {
        var error = new Error(payload.error || '通信に失敗しました。');
        error.status = response.status;
        error.data = payload.data;
        throw error;
      }
      return payload.data;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function formatRelativeDueDate(dueDateStr) {
    if (!dueDateStr) return null;
    var today = new Date();
    today.setHours(0, 0, 0, 0);

    var parts = dueDateStr.split('-');
    if (parts.length !== 3) return { text: '期限 ' + dueDateStr, isOverdue: false, isDueToday: false };

    var dueDate = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    dueDate.setHours(0, 0, 0, 0);

    var diffDays = Math.round((dueDate - today) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
      return { text: '期限切れ (' + Math.abs(diffDays) + '日前)', isOverdue: true, isDueToday: false };
    } else if (diffDays === 0) {
      return { text: '今日が期限', isOverdue: false, isDueToday: true };
    } else if (diffDays === 1) {
      return { text: '明日まで', isOverdue: false, isDueToday: false };
    } else if (diffDays <= 7) {
      return { text: 'あと' + diffDays + '日', isOverdue: false, isDueToday: false };
    } else {
      return { text: '期限 ' + Number(parts[1]) + '/' + Number(parts[2]), isOverdue: false, isDueToday: false };
    }
  }

  modules.core = {
    config: app.api.getConfig('taskBoard'),
    t: t,
    csrf: csrf,
    toast: toast,
    request: request,
    formatRelativeDueDate: formatRelativeDueDate
  };
})(window);
