(function (window) {
  window.GroupRoomModules = window.GroupRoomModules || {};
  var modules = window.GroupRoomModules;

  function getGroupRoomConfig() {
    return window.GroupRoomConfig || {};
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

  function isPlainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
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

  function setProgressScale(progressBar, scale) {
    if (!progressBar) {
      return;
    }
    progressBar.style.transform = `scaleX(${scale})`;
  }

  function getDownloadProgressElements() {
    return {
      spinnerContainer: document.getElementById('downloadSpinnerContainer'),
      animationContainer: document.getElementById('downloadAnimationContainer'),
      statusText: document.getElementById('downloadStatusText'),
      progressBar: document.getElementById('downloadProgressBar')
    };
  }

  function triggerBlobDownload(blob, filename) {
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  }

  function showDownloadProgress(statusText) {
    var elements = getDownloadProgressElements();
    showElement(elements.spinnerContainer);
    if (elements.animationContainer) {
      elements.animationContainer.classList.add('downloading');
    }
    setElementText(elements.statusText, statusText);
    setProgressScale(elements.progressBar, 0);
  }

  function hideDownloadProgress() {
    var elements = getDownloadProgressElements();
    hideElement(elements.spinnerContainer);
    if (elements.animationContainer) {
      elements.animationContainer.classList.remove('downloading');
    }
  }

  function setDownloadProgressScale(scale) {
    var elements = getDownloadProgressElements();
    setProgressScale(elements.progressBar, scale);
  }

  function setDownloadStatusText(text) {
    var elements = getDownloadProgressElements();
    setElementText(elements.statusText, text);
  }

  modules.core = {
    getGroupRoomConfig: getGroupRoomConfig,
    createLogger: createLogger,
    isPlainObject: isPlainObject,
    safeParseJson: safeParseJson,
    getCsrfToken: getCsrfToken,
    createUploadIconController: createUploadIconController,
    showElement: showElement,
    hideElement: hideElement,
    setElementText: setElementText,
    setProgressScale: setProgressScale,
    triggerBlobDownload: triggerBlobDownload,
    showDownloadProgress: showDownloadProgress,
    hideDownloadProgress: hideDownloadProgress,
    setDownloadProgressScale: setDownloadProgressScale,
    setDownloadStatusText: setDownloadStatusText
  };
})(window);
