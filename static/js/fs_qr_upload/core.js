(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function getFsQrUploadConfig() {
    return appNamespace.api.getConfig('fsQrUpload');
  }

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

  function safeParseJson(rawText, logger, label) {
    if (typeof rawText !== 'string') {
      if (logger && typeof logger.warn === 'function') {
        logger.warn(`${label || 'JSON payload'} is not a string.`);
      }
      return null;
    }

    try {
      return JSON.parse(rawText);
    } catch (error) {
      if (logger && typeof logger.warn === 'function') {
        logger.warn(`${label || 'JSON payload'} parse failed.`, error);
      }
      return null;
    }
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  function getElements() {
    return {
      uploadArea: document.getElementById('upload-area'),
      fileInput: document.getElementById('fileInput'),
      fileListDisplay: document.getElementById('fileList'),
      idInput: document.getElementById('name'),
      uploadForm: document.getElementById('uploadForm'),
      startUploadBtn: document.getElementById('startUploadBtn'),
      retentionSelect: document.getElementById('retention'),
      retentionPreviewTime: document.getElementById('retentionPreviewTime'),
      inlineError: document.getElementById('uploadInlineError'),
      spinnerRoot: document.getElementById('uploadProgressContainer'),
      spinnerAnimationContainer: document.getElementById('uploadProgressContainer'),
      spinnerEyebrow: document.getElementById('uploadProgressEyebrow'),
      spinnerText: document.getElementById('uploadProgressText'),
      spinnerProgress: document.getElementById('uploadProgressBar')
    };
  }

  function getCsrfToken() {
    var csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
    return csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';
  }

  function createUploadIconController(icons) {
    var uploadIconElement = document.querySelector('.upload-icon-modern');
    return {
      setUploadIcon: function (name) {
        if (uploadIconElement && icons[name]) {
          uploadIconElement.innerHTML = icons[name];
        }
      }
    };
  }

  function createFormErrorController(inlineError) {
    function showFormError(message) {
      if (!inlineError) {
        return;
      }
      inlineError.textContent = message;
      inlineError.classList.add('is-visible');
    }

    function clearFormError() {
      if (!inlineError) {
        return;
      }
      inlineError.textContent = '';
      inlineError.classList.remove('is-visible');
    }

    return {
      showFormError: showFormError,
      clearFormError: clearFormError
    };
  }

  function setFileInputFiles(fileInput, files) {
    var dataTransfer = new DataTransfer();
    Array.from(files).forEach(function (file) {
      dataTransfer.items.add(file);
    });
    fileInput.files = dataTransfer.files;
  }

  modules.core = {
    getFsQrUploadConfig: getFsQrUploadConfig,
    createLogger: createLogger,
    safeParseJson: safeParseJson,
    isPlainObject: isPlainObject,
    getElements: getElements,
    getCsrfToken: getCsrfToken,
    createUploadIconController: createUploadIconController,
    createFormErrorController: createFormErrorController,
    setFileInputFiles: setFileInputFiles
  };
})(window);
