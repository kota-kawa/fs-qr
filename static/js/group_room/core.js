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

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
  }

  function setupAjaxCsrf(csrfToken) {
    $.ajaxSetup({
      beforeSend: function (xhr) {
        xhr.setRequestHeader('X-CSRF-Token', csrfToken);
      }
    });
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
    $('#downloadSpinnerContainer').show();
    $('#downloadAnimationContainer').addClass('downloading');
    $('#downloadStatusText').text(statusText);
    $('#downloadProgressBar').css('transform', 'scaleX(0)');
  }

  function hideDownloadProgress() {
    $('#downloadSpinnerContainer').hide();
    $('#downloadAnimationContainer').removeClass('downloading');
  }

  function setDownloadProgressScale(scale) {
    $('#downloadProgressBar').css('transform', `scaleX(${scale})`);
  }

  function setDownloadStatusText(text) {
    $('#downloadStatusText').text(text);
  }

  modules.core = {
    getGroupRoomConfig: getGroupRoomConfig,
    createLogger: createLogger,
    getCsrfToken: getCsrfToken,
    setupAjaxCsrf: setupAjaxCsrf,
    createUploadIconController: createUploadIconController,
    triggerBlobDownload: triggerBlobDownload,
    showDownloadProgress: showDownloadProgress,
    hideDownloadProgress: hideDownloadProgress,
    setDownloadProgressScale: setDownloadProgressScale,
    setDownloadStatusText: setDownloadStatusText
  };
})(window);
