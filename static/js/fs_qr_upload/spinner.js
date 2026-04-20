(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function createSpinnerController(options) {
    var spinnerRoot = options.spinnerRoot;
    var spinnerAnimationContainer = options.spinnerAnimationContainer;
    var spinnerEyebrow = options.spinnerEyebrow;
    var spinnerText = options.spinnerText;
    var spinnerProgress = options.spinnerProgress;

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
      if (spinnerEyebrow) {
        spinnerEyebrow.textContent = 'Encrypting';
      }
      if (spinnerText) {
        spinnerText.textContent = '暗号化中...';
      }
    }

    function showSpinner() {
      if (spinnerRoot) {
        spinnerRoot.style.display = 'grid';
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

    function setProgressScale(scale) {
      if (spinnerProgress) {
        spinnerProgress.style.transform = `scaleX(${scale})`;
      }
    }

    function startEncryptionAnimation() {
      setPhase('encrypting');
      setSpinnerEyebrow('Encrypting');
    }

    function startUploadAnimation() {
      setPhase('uploading');
      setSpinnerEyebrow('Uploading');
    }

    function stopIconSwitching() {
      setPhase('');
    }

    return {
      hideSpinner: hideSpinner,
      showSpinner: showSpinner,
      setSpinnerText: setSpinnerText,
      setSpinnerEyebrow: setSpinnerEyebrow,
      setProgressScale: setProgressScale,
      startEncryptionAnimation: startEncryptionAnimation,
      startUploadAnimation: startUploadAnimation,
      stopIconSwitching: stopIconSwitching
    };
  }

  modules.spinner = {
    createSpinnerController: createSpinnerController
  };
})(window);
