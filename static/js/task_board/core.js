(function (window) {
  'use strict';

  var app = window.__FSQR_APP__;
  if (!app || !app.api) {
    throw new Error('App namespace is not initialized.');
  }

  var modules = app.api.getModuleNamespace('taskBoard');

  var STATUSES = ['todo', 'doing', 'done'];
  var STATUS_LABELS = {
    todo: '未着手',
    doing: '進行中',
    done: '完了'
  };
  var PRIORITY_LABELS = {
    high: '高',
    normal: '通常',
    low: '低'
  };

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
      return window.FSQRUx.toast(message, { type: type || 'info' });
    }
    return null;
  }

  /**
   * Toast with an inline "undo" action.
   * 取り消し操作つきのトースト。削除など復元可能な操作で使う。
   */
  function toastWithUndo(message, onUndo, options) {
    options = options || {};
    var handle = null;
    if (window.FSQRUx && typeof window.FSQRUx.toast === 'function') {
      handle = window.FSQRUx.toast(message, {
        type: options.type || 'success',
        duration: options.duration || 8000
      });
    }
    if (!handle || !handle.node) {
      return null;
    }

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'task-toast-undo';
    button.textContent = '元に戻す';
    button.addEventListener('click', function (event) {
      event.stopPropagation();
      handle.dismiss();
      try {
        onUndo();
      } catch (err) {
        console.error('Task undo failed:', err);
      }
    });
    handle.node.appendChild(button);
    return handle;
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

  function itemsUrl(suffix) {
    return (
      '/api/task/' +
      encodeURIComponent(modules.core.config.roomId) +
      '/items' +
      (suffix || '')
    );
  }

  /**
   * Days between today and the due date. Returns null when unset/invalid.
   * 期限日までの残り日数。未設定・不正な値のときは null。
   */
  function dueDiffDays(dueDateStr) {
    if (!dueDateStr) return null;
    var parts = String(dueDateStr).split('-');
    if (parts.length !== 3) return null;

    var dueDate = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    if (isNaN(dueDate.getTime())) return null;
    dueDate.setHours(0, 0, 0, 0);

    var today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.round((dueDate - today) / (1000 * 60 * 60 * 24));
  }

  function formatRelativeDueDate(dueDateStr) {
    if (!dueDateStr) return null;
    var diffDays = dueDiffDays(dueDateStr);
    var parts = String(dueDateStr).split('-');

    if (diffDays === null) {
      return { text: '期限 ' + dueDateStr, isOverdue: false, isDueToday: false, diffDays: null };
    }
    if (diffDays < 0) {
      return {
        text: '期限切れ (' + Math.abs(diffDays) + '日前)',
        isOverdue: true,
        isDueToday: false,
        diffDays: diffDays
      };
    }
    if (diffDays === 0) {
      return { text: '今日が期限', isOverdue: false, isDueToday: true, diffDays: 0 };
    }
    if (diffDays === 1) {
      return { text: '明日まで', isOverdue: false, isDueToday: false, diffDays: 1 };
    }
    if (diffDays <= 7) {
      return { text: 'あと' + diffDays + '日', isOverdue: false, isDueToday: false, diffDays: diffDays };
    }
    return {
      text: '期限 ' + Number(parts[1]) + '/' + Number(parts[2]),
      isOverdue: false,
      isDueToday: false,
      diffDays: diffDays
    };
  }

  /** Inline SVG helper for dynamically built controls. / 動的生成UI用のSVGヘルパー。 */
  var ICON_PATHS = {
    edit: 'M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z',
    trash: 'M8.75 3.5a.75.75 0 00-.75.75V5h4v-.75a.75.75 0 00-.75-.75h-2.5zM14.5 5v-.75A2.25 2.25 0 0012.25 2h-2.5A2.25 2.25 0 007.5 4.25V5H4.75a.75.75 0 000 1.5h.61l.66 8.58A2.25 2.25 0 008.27 17h5.46a2.25 2.25 0 002.25-1.92l.66-8.58h.61a.75.75 0 000-1.5H14.5z',
    arrowLeft: 'M11.78 5.22a.75.75 0 010 1.06L8.06 10l3.72 3.72a.75.75 0 11-1.06 1.06l-4.25-4.25a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 0z',
    arrowRight: 'M8.22 5.22a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 11-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 010-1.06z',
    arrowUp: 'M10 4.5a.75.75 0 01.53.22l4.25 4.25a.75.75 0 11-1.06 1.06L10 6.31l-3.72 3.72a.75.75 0 01-1.06-1.06l4.25-4.25A.75.75 0 0110 4.5z',
    arrowDown: 'M10 15.5a.75.75 0 01-.53-.22l-4.25-4.25a.75.75 0 111.06-1.06L10 13.69l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-.53.22z',
    plus: 'M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z',
    collapse: 'M4.25 9.25h11.5a.75.75 0 010 1.5H4.25a.75.75 0 010-1.5z',
    broom: 'M4.5 15.5a.75.75 0 01.75-.75h9.5a.75.75 0 010 1.5h-9.5a.75.75 0 01-.75-.75zm2.28-3.03l5.69-5.69 2.75 2.75-5.69 5.69H6.78v-2.75zm7.5-6.75l1.06-1.06a1.5 1.5 0 012.12 2.12l-1.06 1.06-2.12-2.12z'
  };

  function icon(name) {
    var path = ICON_PATHS[name];
    if (!path) return null;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 20 20');
    svg.setAttribute('fill', 'currentColor');
    svg.setAttribute('aria-hidden', 'true');
    var node = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    node.setAttribute('d', path);
    svg.appendChild(node);
    return svg;
  }

  modules.core = {
    config: app.api.getConfig('taskBoard'),
    STATUSES: STATUSES,
    STATUS_LABELS: STATUS_LABELS,
    PRIORITY_LABELS: PRIORITY_LABELS,
    t: t,
    csrf: csrf,
    icon: icon,
    toast: toast,
    toastWithUndo: toastWithUndo,
    request: request,
    itemsUrl: itemsUrl,
    dueDiffDays: dueDiffDays,
    formatRelativeDueDate: formatRelativeDueDate
  };
})(window);
