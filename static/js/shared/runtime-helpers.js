/**
 * Shared runtime helpers for the vanilla JS bundles.
 * 各画面のバンドルが個別に持っていた翻訳・ログ・DOM 操作の小さな共通処理をまとめる。
 *
 * Loaded after app-namespace.js and exposed through
 * `window.__FSQR_APP__.api.getShared('runtimeHelpers')`.
 */
(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }

  /** Translate through window.FSQR_I18N when available. / FSQR_I18N があれば翻訳し、無ければ fallback を返す。 */
  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function') {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  function escapeRegExp(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * Translate and fill placeholders.
   * `{name}` と `%(name)s` の両方の書式を置換する（Task の翻訳カタログは後者を使う）。
   */
  function formatMessage(key, fallback, replacements) {
    var message = translate(key, fallback);
    Object.keys(replacements || {}).forEach(function (name) {
      var value = String(replacements[name]);
      var escaped = escapeRegExp(name);
      message = message
        .replace(new RegExp('\\{' + escaped + '\\}', 'g'), value)
        .replace(new RegExp('%\\(' + escaped + '\\)s', 'g'), value);
    });
    return message;
  }

  /** Console logger that stays silent unless debugging is enabled. / debug 時のみ出力するロガー。 */
  function createLogger(enabled) {
    function callConsole(method, args) {
      if (!enabled || typeof window.console === 'undefined') {
        return;
      }
      if (typeof window.console[method] === 'function') {
        window.console[method].apply(window.console, args);
        return;
      }
      if (typeof window.console.log === 'function') {
        window.console.log.apply(window.console, args);
      }
    }

    return {
      log: function () {
        callConsole('log', arguments);
      },
      warn: function () {
        callConsole('warn', arguments);
      },
      error: function () {
        callConsole('error', arguments);
      }
    };
  }

  /** Read the CSRF token from the meta tag. / meta タグから CSRF トークンを読む。 */
  function getCsrfToken() {
    var csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
    return csrfTokenMeta ? (csrfTokenMeta.getAttribute('content') || '') : '';
  }

  /** JSON.parse that never throws; parse failures are logged through the optional logger. / 例外を投げない JSON.parse。 */
  function safeParseJson(rawText, logger, label) {
    if (typeof rawText !== 'string') {
      if (logger && typeof logger.warn === 'function') {
        logger.warn((label || 'JSON payload') + ' is not a string.');
      }
      return null;
    }

    try {
      return JSON.parse(rawText);
    } catch (error) {
      if (logger && typeof logger.warn === 'function') {
        logger.warn((label || 'JSON payload') + ' parse failed.', error);
      }
      return null;
    }
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  // --- Small DOM helpers / DOM 操作の小道具 ---

  function showElement(element) {
    if (!element) {
      return;
    }
    element.style.removeProperty('display');
  }

  function hideElement(element) {
    if (!element) {
      return;
    }
    element.style.display = 'none';
  }

  function setElementText(element, text) {
    if (!element) {
      return;
    }
    element.textContent = text;
  }

  /** Progress bars are animated with transform: scaleX(). / 進捗バーは scaleX で伸縮させる。 */
  function setProgressScale(progressBar, scale) {
    if (!progressBar) {
      return;
    }
    progressBar.style.transform = 'scaleX(' + scale + ')';
  }

  var runtimeHelpers = Object.freeze({
    translate: translate,
    formatMessage: formatMessage,
    createLogger: createLogger,
    getCsrfToken: getCsrfToken,
    safeParseJson: safeParseJson,
    isPlainObject: isPlainObject,
    showElement: showElement,
    hideElement: hideElement,
    setElementText: setElementText,
    setProgressScale: setProgressScale
  });

  appNamespace.api.setShared('runtimeHelpers', runtimeHelpers);
})(window);
