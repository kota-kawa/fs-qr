/**
 * Shared context for the FSQR download page (elements, config, progress UI).
 * FSQR のダウンロード画面が使う DOM 要素・設定・進捗表示をまとめる。
 *
 * The decryption key is taken from the URL fragment first (#key= / #pw=), then
 * from the server-rendered password, and finally from the legacy secure-id prefix.
 * 復号鍵は URL フラグメント → サーバー描画のパスワード → 旧方式の ID 先頭、の順で決める。
 * See docs/decisions/0004-browser-side-fsqr-encryption.md
 */
(function (window, document) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrDownload');
  var helpers = appNamespace.api.getShared('runtimeHelpers');
  if (!helpers) {
    throw new Error('Shared runtime helpers are not initialized.');
  }
  var progressSpinner = appNamespace.api.getShared('progressSpinner');
  if (!progressSpinner) {
    throw new Error('Shared progress spinner is not initialized.');
  }

  function createContext() {
    var config = appNamespace.api.getConfig('fsQrDownload');
    var secureId = typeof config.secureId === 'string' ? config.secureId : '';
    var serverPassword = config.password == null ? '' : String(config.password);
    var requiresFragmentKey = config.encryptionMode === 'raw';

    var shareParams = new URLSearchParams((window.location.hash || '').replace(/^#/, ''));
    var fragmentKey = shareParams.get('key') || '';
    var fragmentPassword = shareParams.get('pw') || '';

    var spinner = progressSpinner.createProgressSpinner({
      root: document.getElementById('spinnerContainer'),
      displayValue: 'flex',
      hiddenClass: 'spinner-container--hidden',
      animationContainer: document.getElementById('animationContainer'),
      phases: {
        receiving: { className: 'is-receiving', eyebrow: 'Downloading' },
        decrypting: { className: 'is-decrypting', eyebrow: 'Decrypting' }
      },
      eyebrow: document.getElementById('statusEyebrow'),
      text: document.getElementById('statusText'),
      bars: { primary: document.getElementById('progressBar') }
    });

    /** Progress is expressed as a 0..1 scale on the bar. / 進捗は 0〜1 のスケールで表す。 */
    function setProgress(value) {
      spinner.setProgress(Math.max(0, Math.min(1, value)));
    }

    function showSpinner(message, phase) {
      spinner.show();
      spinner.setPhase(phase);
      spinner.setText(message);
    }

    function hideSpinner() {
      spinner.hide();
      spinner.setPhase('');
      setProgress(0);
    }

    var decryptionKey = fragmentKey || (requiresFragmentKey
      ? ''
      : (fragmentPassword || serverPassword || secureId.split('-')[0]));
    var decryptionKeyMode = fragmentKey
      ? 'raw-base64url'
      : ((fragmentPassword || serverPassword) && !requiresFragmentKey ? 'password' : 'legacy-id');

    return {
      downloadForm: document.getElementById('downloadForm'),
      secureId: secureId,
      decryptionKey: decryptionKey,
      decryptionKeyMode: decryptionKeyMode,
      requiresFragmentKey: requiresFragmentKey,
      translate: helpers.translate,
      formatMessage: helpers.formatMessage,
      setStatusText: function (text) {
        spinner.setText(text);
      },
      setProgress: setProgress,
      showSpinner: showSpinner,
      hideSpinner: hideSpinner
    };
  }

  modules.core = {
    createContext: createContext
  };
})(window, document);
