(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function createSpinnerController(options) {
    var spinnerRoot = options.spinnerRoot;
    var spinnerText = options.spinnerText;
    var spinnerProgress = options.spinnerProgress;
    var iconSwitchInterval;

    function hideSpinner() {
      if (spinnerRoot) {
        spinnerRoot.style.display = 'none';
      }
      if (spinnerProgress) {
        spinnerProgress.style.transform = 'scaleX(0)';
      }
      if (spinnerText) {
        spinnerText.textContent = '暗号化中...';
      }
    }

    function showSpinner() {
      if (spinnerRoot) {
        spinnerRoot.style.display = 'flex';
      }
    }

    function setSpinnerText(text) {
      if (spinnerText) {
        spinnerText.textContent = text;
      }
    }

    function setProgressScale(scale) {
      if (spinnerProgress) {
        spinnerProgress.style.transform = `scaleX(${scale})`;
      }
    }

    function startEncryptionAnimation() {
      var spinnerContainer = document.querySelector('.spinner-second-container');
      iconSwitchInterval = setInterval(function () {
        spinnerContainer.classList.toggle('encrypting');
      }, 1000);
    }

    function startUploadAnimation() {
      var spinnerContainer = document.querySelector('.spinner-second-container');
      clearInterval(iconSwitchInterval);
      spinnerContainer.classList.remove('encrypting');

      iconSwitchInterval = setInterval(function () {
        spinnerContainer.classList.toggle('uploading');
      }, 800);
    }

    function stopIconSwitching() {
      clearInterval(iconSwitchInterval);
    }

    return {
      hideSpinner: hideSpinner,
      showSpinner: showSpinner,
      setSpinnerText: setSpinnerText,
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
