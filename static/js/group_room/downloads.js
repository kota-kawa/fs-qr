(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');

  function createDownloadHandlers(options) {
    var roomId = options.roomId;
    var downloadAllBtn = options.downloadAllBtn;
    var core = options.core;

    var isDownloading = {};
    var isDownloadingAll = false;

    function translate(key, fallback) {
      return core.translate ? core.translate(key, fallback) : fallback;
    }

    function formatMessage(key, fallback, replacements) {
      return core.formatMessage ? core.formatMessage(key, fallback, replacements) : fallback.replace(/\{([^}]+)\}/g, function (_, name) {
        return Object.prototype.hasOwnProperty.call(replacements || {}, name) ? String(replacements[name]) : `{${name}}`;
      });
    }

    function notify(message) {
      if (typeof window.showAlertModal === 'function') {
        window.showAlertModal(message);
        return;
      }
      window.alert(message);
    }

    function downloadSingleFile(file, downloadBtn) {
      var encodedFilename = encodeURIComponent(file.name);
      var downloadKey = `${roomId}-${file.name}`;

      if (isDownloading[downloadKey]) {
        return;
      }

      isDownloading[downloadKey] = true;
      downloadBtn.disabled = true;
      core.showDownloadProgress(formatMessage('download.single_progress', 'Downloading {name}... {percent}%', { name: file.name, percent: 0 }));

      var xhr = new XMLHttpRequest();
      xhr.open('GET', `/download/${roomId}/${encodedFilename}`, true);
      xhr.responseType = 'blob';

      xhr.onprogress = function (event) {
        if (event.lengthComputable) {
          var percentComplete = event.loaded / event.total;
          core.setDownloadProgressScale(percentComplete);
          core.setDownloadStatusText(formatMessage('download.single_progress', 'Downloading {name}... {percent}%', { name: file.name, percent: Math.round(percentComplete * 100) }));
        }
      };

      xhr.onload = function () {
        if (xhr.status === 200) {
          core.triggerBlobDownload(xhr.response, file.name);
          core.setDownloadProgressScale(1);
          core.setDownloadStatusText(translate('download.complete', 'Download complete!'));
          setTimeout(function () {
            core.hideDownloadProgress();
          }, 1000);
        } else {
          notify(translate('download.error', 'An error occurred during download.'));
          core.hideDownloadProgress();
        }
        isDownloading[downloadKey] = false;
        downloadBtn.disabled = false;
      };

      xhr.onerror = function () {
        notify(translate('download.error', 'An error occurred during download.'));
        core.hideDownloadProgress();
        isDownloading[downloadKey] = false;
        downloadBtn.disabled = false;
      };

      xhr.send();
    }

    function downloadAllFiles() {
      if (isDownloadingAll) {
        return;
      }

      var fileCountEl = document.getElementById('fileCount');
      var fileCount = fileCountEl ? parseInt(fileCountEl.textContent, 10) : 0;
      if (fileCount === 0) {
        notify(translate('download.no_files', 'There are no files to download.'));
        return;
      }

      isDownloadingAll = true;
      downloadAllBtn.disabled = true;
      core.showDownloadProgress(formatMessage('download.all_progress', 'Downloading all files... {percent}%', { percent: 0 }));

      var xhr = new XMLHttpRequest();
      xhr.open('GET', `/download/all/${roomId}`, true);
      xhr.responseType = 'blob';

      xhr.onprogress = function (event) {
        if (event.lengthComputable) {
          var percentComplete = event.loaded / event.total;
          core.setDownloadProgressScale(percentComplete);
          core.setDownloadStatusText(formatMessage('download.all_progress', 'Downloading all files... {percent}%', { percent: Math.round(percentComplete * 100) }));
        }
      };

      xhr.onload = function () {
        if (xhr.status === 200) {
          core.triggerBlobDownload(xhr.response, `${roomId}_files.zip`);
          core.setDownloadProgressScale(1);
          core.setDownloadStatusText(translate('download.complete', 'Download complete!'));
          setTimeout(function () {
            core.hideDownloadProgress();
          }, 1000);
        } else {
          notify(translate('download.error', 'An error occurred during download.'));
          core.hideDownloadProgress();
        }

        isDownloadingAll = false;
        downloadAllBtn.disabled = false;
      };

      xhr.onerror = function () {
        notify(translate('download.error', 'An error occurred during download.'));
        core.hideDownloadProgress();
        isDownloadingAll = false;
        downloadAllBtn.disabled = false;
      };

      xhr.send();
    }

    return {
      downloadSingleFile: downloadSingleFile,
      bindDownloadAll: function () {
        downloadAllBtn.addEventListener('click', downloadAllFiles);
      }
    };
  }

  modules.downloads = {
    createDownloadHandlers: createDownloadHandlers
  };
})(window);
