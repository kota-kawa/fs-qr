(function (window) {
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
    var spinnerRoot = options.spinnerRoot;
    var spinnerAnimationContainer = options.spinnerAnimationContainer;
    var spinnerEyebrow = options.spinnerEyebrow;
    var spinnerText = options.spinnerText;
    var spinnerDetail = options.spinnerDetail;
    var spinnerProgress = options.spinnerProgress;
    var uploadProgress = options.uploadProgress;

    function setPhase(phaseName) {
      if (!spinnerAnimationContainer) {
        return;
      }
      spinnerAnimationContainer.classList.remove('is-encrypting', 'is-uploading');
      if (phaseName === 'encrypting') {
        spinnerAnimationContainer.classList.add('is-encrypting');
      } else if (phaseName === 'uploading') {
        spinnerAnimationContainer.classList.add('is-uploading');
      }
    }

    function hideSpinner() {
      if (spinnerRoot) {
        spinnerRoot.style.display = 'none';
      }
      setPhase('');
      if (spinnerProgress) {
        spinnerProgress.style.transform = 'scaleX(0)';
      }
      if (uploadProgress) {
        uploadProgress.style.transform = 'scaleX(0)';
      }
      if (spinnerEyebrow) {
        spinnerEyebrow.textContent = translate('upload.encryption', 'Encryption');
      }
      if (spinnerText) {
        spinnerText.textContent = translate('upload.encrypting', 'Encrypting...');
      }
      if (spinnerDetail) {
        spinnerDetail.textContent = translate('upload.preparing', 'Preparing files.');
      }
    }

    function scrollSpinnerIntoCenter() {
      if (!spinnerRoot || typeof spinnerRoot.scrollIntoView !== 'function') {
        return;
      }
      window.requestAnimationFrame(function () {
        try {
          spinnerRoot.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch (error) {
          spinnerRoot.scrollIntoView(true);
        }
      });
    }

    function showSpinner() {
      if (spinnerRoot) {
        spinnerRoot.style.display = 'grid';
        scrollSpinnerIntoCenter();
      }
    }

    function setSpinnerText(text) {
      if (spinnerText) {
        spinnerText.textContent = text;
      }
    }

    function setSpinnerEyebrow(text) {
      if (spinnerEyebrow) {
        spinnerEyebrow.textContent = text;
      }
    }

    function setSpinnerDetail(text) {
      if (spinnerDetail) {
        spinnerDetail.textContent = text;
      }
    }

    function setProgressScale(scale) {
      if (spinnerProgress) {
        spinnerProgress.style.transform = `scaleX(${scale})`;
      }
    }

    function setUploadProgressScale(scale) {
      if (uploadProgress) {
        uploadProgress.style.transform = `scaleX(${scale})`;
      }
    }

    function startEncryptionAnimation() {
      setPhase('encrypting');
      setSpinnerEyebrow(translate('upload.encryption', 'Encryption'));
      setUploadProgressScale(0);
    }

    function startUploadAnimation() {
      setPhase('uploading');
      setSpinnerEyebrow(translate('upload.upload', 'Upload'));
      setProgressScale(1);
    }

    function stopIconSwitching() {
      setPhase('');
    }

    return {
      hideSpinner: hideSpinner,
      showSpinner: showSpinner,
      setSpinnerText: setSpinnerText,
      setSpinnerEyebrow: setSpinnerEyebrow,
      setSpinnerDetail: setSpinnerDetail,
      setProgressScale: setProgressScale,
      setUploadProgressScale: setUploadProgressScale,
      startEncryptionAnimation: startEncryptionAnimation,
      startUploadAnimation: startUploadAnimation,
      stopIconSwitching: stopIconSwitching
    };
  }

  modules.spinner = {
    createSpinnerController: createSpinnerController
  };
})(window);
