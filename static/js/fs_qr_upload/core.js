(function (window) {
  window.FsQrUploadModules = window.FsQrUploadModules || {};
  var modules = window.FsQrUploadModules;

  function getFsQrUploadConfig() {
    return window.FsQrUploadConfig || {};
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
      spinnerRoot: document.getElementById('spinner-container'),
      spinnerText: document.querySelector('#spinner-container .text'),
      spinnerProgress: document.querySelector('#spinner-container .progress-bar')
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
    getElements: getElements,
    getCsrfToken: getCsrfToken,
    createUploadIconController: createUploadIconController,
    createFormErrorController: createFormErrorController,
    setFileInputFiles: setFileInputFiles
  };
})(window);
