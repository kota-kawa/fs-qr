/**
 * Encrypted blob download (XHR with progress) for the FSQR download page.
 * 暗号化済みファイルの取得。進捗表示のため fetch ではなく XHR を使う。
 */
(function (window, document) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrDownload');
  var helpers = appNamespace.api.getShared('runtimeHelpers');

  function createTransferService(context) {
    function downloadEncryptedBlob() {
      return new Promise(function (resolve, reject) {
        var csrfToken = helpers.getCsrfToken();
        var xhr = new XMLHttpRequest();
        xhr.open('POST', context.downloadForm.action, true);
        xhr.responseType = 'blob';
        if (csrfToken) {
          xhr.setRequestHeader('X-CSRF-Token', csrfToken);
        }

        xhr.onprogress = function (event) {
          if (event.lengthComputable) {
            var percent = event.loaded / event.total;
            context.setProgress(percent);
            context.setStatusText(
              context.formatMessage(
                'download.downloading_progress',
                'Downloading... {percent}%',
                { percent: Math.round(percent * 100) }
              )
            );
          }
        };

        xhr.onload = function () {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve({
              blob: xhr.response,
              fileType: xhr.getResponseHeader('X-File-Type') || 'multiple',
              originalFilename: xhr.getResponseHeader('X-Original-Filename') || ''
            });
            return;
          }
          reject(new Error(context.translate('download.failed', 'Download failed.')));
        };

        xhr.onerror = function () {
          reject(new Error(context.translate('download.failed', 'Download failed.')));
        };

        xhr.send();
      });
    }

    /** Hand the decrypted blob to the browser as a file. / 復号済みの Blob をファイルとして保存させる。 */
    function saveBlob(blob, filename) {
      var objectUrl = URL.createObjectURL(blob);
      var link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.setTimeout(function () {
        URL.revokeObjectURL(objectUrl);
      }, 1000);
    }

    return {
      downloadEncryptedBlob: downloadEncryptedBlob,
      saveBlob: saveBlob
    };
  }

  modules.transfer = {
    createTransferService: createTransferService
  };
})(window, document);
