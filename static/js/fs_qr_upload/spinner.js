/**
 * FSQR upload spinner adapter.
 * フェーズ切替・進捗バー更新は shared/progress-spinner.js に委譲する。
 */
(function (window) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function') {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  function createSpinnerController(options) {
    var shared = appNamespace.api.getShared('progressSpinner');
    if (!shared) {
      throw new Error('Shared progress spinner is not initialized.');
    }
    var controller = shared.createProgressSpinner({
      root: options.spinnerRoot,
      displayValue: 'grid',
      animationContainer: options.spinnerAnimationContainer,
      eyebrow: options.spinnerEyebrow,
      text: options.spinnerText,
      detail: options.spinnerDetail,
      bars: {
        encryption: options.spinnerProgress,
        upload: options.uploadProgress
      },
      phases: {
        // eyebrow は関数で渡し、setPhase() が実際に呼ばれる（＝アップロード開始操作の）
        // 時点で translate() を評価する。ここでトップレベル評価すると、
        // window.FSQR_I18N（cookie-consent.html 側で定義）がまだ読み込まれておらず
        // 常に英語フォールバックになってしまう。
        // eyebrow is a function so translate() runs when setPhase() actually fires
        // (i.e. when the user starts the upload), not at script-load time — evaluating
        // it here would run before window.FSQR_I18N (defined in cookie-consent.html)
        // is ready and always fall back to English.
        encrypting: {
          className: 'is-encrypting',
          eyebrow: function () { return translate('upload.encryption', 'Encryption'); }
        },
        uploading: {
          className: 'is-uploading',
          eyebrow: function () { return translate('upload.upload', 'Upload'); }
        }
      }
    });

    function hideSpinner() {
      controller.hide();
      controller.setPhase('');
      controller.resetProgress();
      controller.setEyebrow(translate('upload.encryption', 'Encryption'));
      controller.setText(translate('upload.encrypting', 'Encrypting...'));
      controller.setDetail(translate('upload.preparing', 'Preparing files.'));
    }

    function setProgressScale(scale) {
      controller.setProgress(scale, 'encryption');
    }

    function setUploadProgressScale(scale) {
      controller.setProgress(scale, 'upload');
    }

    function startEncryptionAnimation() {
      controller.setPhase('encrypting');
      controller.setProgress(0, 'upload');
    }

    function startUploadAnimation() {
      controller.setPhase('uploading');
      controller.setProgress(1, 'encryption');
    }

    return {
      hideSpinner: hideSpinner,
      showSpinner: function () {
        controller.show();
        controller.scrollIntoCenter();
      },
      setSpinnerText: controller.setText,
      setSpinnerEyebrow: controller.setEyebrow,
      setSpinnerDetail: controller.setDetail,
      setProgressScale: setProgressScale,
      setUploadProgressScale: setUploadProgressScale,
      startEncryptionAnimation: startEncryptionAnimation,
      startUploadAnimation: startUploadAnimation,
      stopIconSwitching: function () { controller.setPhase(''); }
    };
  }

  modules.spinner = {
    createSpinnerController: createSpinnerController
  };
})(window);
