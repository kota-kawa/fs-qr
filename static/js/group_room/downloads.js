(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');

  function createDownloadHandlers(options) {
    var roomId = options.roomId;
    var roomPassword = options.roomPassword;
    var downloadAllBtn = options.downloadAllBtn;
    var core = options.core;

    var isDownloading = {};
    var isDownloadingAll = false;

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
      core.showDownloadProgress(`${file.name} をダウンロード中... 0%`);

      var xhr = new XMLHttpRequest();
      xhr.open('GET', `/download/${roomId}/${roomPassword}/${encodedFilename}`, true);
      xhr.responseType = 'blob';

      xhr.onprogress = function (event) {
        if (event.lengthComputable) {
          var percentComplete = event.loaded / event.total;
          core.setDownloadProgressScale(percentComplete);
          core.setDownloadStatusText(`${file.name} をダウンロード中... ${Math.round(percentComplete * 100)}%`);
        }
      };

      xhr.onload = function () {
        if (xhr.status === 200) {
          core.triggerBlobDownload(xhr.response, file.name);
          core.setDownloadProgressScale(1);
          core.setDownloadStatusText('ダウンロード完了！');
          setTimeout(function () {
            core.hideDownloadProgress();
          }, 1000);
        } else {
          notify('ダウンロード中にエラーが発生しました。');
          core.hideDownloadProgress();
        }
        isDownloading[downloadKey] = false;
        downloadBtn.disabled = false;
      };

      xhr.onerror = function () {
        notify('ダウンロード中にエラーが発生しました。');
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

      isDownloadingAll = true;
      downloadAllBtn.disabled = true;
      core.showDownloadProgress('全ファイルをダウンロード中... 0%');

      var xhr = new XMLHttpRequest();
      xhr.open('GET', `/download/all/${roomId}/${roomPassword}`, true);
      xhr.responseType = 'blob';

      xhr.onprogress = function (event) {
        if (event.lengthComputable) {
          var percentComplete = event.loaded / event.total;
          core.setDownloadProgressScale(percentComplete);
          core.setDownloadStatusText(`全ファイルをダウンロード中... ${Math.round(percentComplete * 100)}%`);
        }
      };

      xhr.onload = function () {
        if (xhr.status === 200) {
          core.triggerBlobDownload(xhr.response, `${roomId}_files.zip`);
          core.setDownloadProgressScale(1);
          core.setDownloadStatusText('ダウンロード完了！');
          setTimeout(function () {
            core.hideDownloadProgress();
          }, 1000);
        } else {
          notify('ダウンロード中にエラーが発生しました。');
          core.hideDownloadProgress();
        }

        isDownloadingAll = false;
        downloadAllBtn.disabled = false;
      };

      xhr.onerror = function () {
        notify('ダウンロード中にエラーが発生しました。');
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
