(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');

  function createUploadSubmitter(options) {
    var uploadBtn = options.uploadBtn;
    var uploadStatusMessage = options.uploadStatusMessage;
    var uploadButtonLabel = options.uploadButtonLabel;
    var roomId = options.roomId;
    var roomPassword = options.roomPassword;
    var csrfToken = options.csrfToken;
    var core = options.core;
    var getFiles = options.getFiles;
    var clearFiles = options.clearFiles;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var refreshRemoteFiles = typeof options.refreshRemoteFiles === 'function'
      ? options.refreshRemoteFiles
      : function () {};
    var validation = appNamespace.api.getShared('uploadValidation');
    if (!validation) {
      throw new Error('Shared upload validation is not initialized.');
    }
    var limits = validation.normalizeLimits(options.limits || {});
    var uploadProgressContainer = document.getElementById('uploadProgressContainer');
    var uploadProgressBar = document.getElementById('uploadProgressBar');
    var uploadProgressText = document.getElementById('uploadProgressText');

    function parseJsonResponse(rawText, label) {
      var parsed = core.safeParseJson
        ? core.safeParseJson(rawText, logger, label)
        : null;
      return parsed;
    }

    function isUploadResponsePayload(payload) {
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        return false;
      }
      if (payload.status !== 'ok' && payload.status !== 'error') {
        return false;
      }
      if (payload.data !== undefined && (!payload.data || typeof payload.data !== 'object' || Array.isArray(payload.data))) {
        return false;
      }
      if (payload.error !== undefined && payload.error !== null && typeof payload.error !== 'string') {
        return false;
      }
      if (payload.data && payload.data.message !== undefined && typeof payload.data.message !== 'string') {
        return false;
      }
      if (payload.data && payload.data.files !== undefined && !Array.isArray(payload.data.files)) {
        return false;
      }
      return true;
    }

    function showStatusMessage(message, isError) {
      uploadStatusMessage.textContent = message;
      uploadStatusMessage.classList.toggle('is-error', Boolean(isError));
      uploadStatusMessage.style.display = 'block';
    }

    function resetStatusMessage() {
      uploadStatusMessage.classList.remove('is-error');
      uploadStatusMessage.style.display = 'none';
      uploadStatusMessage.textContent = '';
    }

    function validateFiles(filesArray) {
      if (filesArray.length === 0) {
        alert('アップロードするファイルがありません。');
        return false;
      }

      var result = validation.validateSelection(filesArray, limits, {
        checkFileName: true
      });
      if (!result.ok) {
        if (result.reason === 'max_files') {
          alert(`ファイル数は最大${limits.maxFiles}個までです`);
        } else if (result.reason === 'max_total_size') {
          alert(`ファイルの合計サイズは${limits.maxTotalSizeMB}MBまでです（現在: ${result.totalSizeMB}MB）`);
        } else if (result.reason === 'invalid_filename') {
          alert('不正なファイル名が含まれています。ファイル名を変更して再度お試しください。');
        }
        return false;
      }

      return true;
    }

    function buildUploadFormData(filesArray) {
      var formData = new FormData();
      filesArray.forEach(function (file) {
        formData.append('upfile', file);
      });
      return formData;
    }

    function showUploadProgressStart() {
      core.showElement(uploadProgressContainer);
      core.setProgressScale(uploadProgressBar, 0);
      core.setElementText(uploadProgressText, 'アップロード中...');
      resetStatusMessage();
      uploadBtn.disabled = true;
      uploadBtn.textContent = 'アップロード中...';
    }

    function showUploadError(xhr) {
      core.hideElement(uploadProgressContainer);
      uploadBtn.disabled = false;
      uploadBtn.innerHTML = uploadButtonLabel;

      var errorMessage = 'アップロード中にエラーが発生しました。';
      if (xhr && xhr.responseText) {
        var responseJson = parseJsonResponse(xhr.responseText, 'group upload error');
        if (responseJson && typeof responseJson.error === 'string' && responseJson.error) {
          errorMessage = responseJson.error;
        }
      }

      showStatusMessage(errorMessage, true);
    }

    function handleUploadResponse(response) {
      core.setProgressScale(uploadProgressBar, 1);
      core.setElementText(uploadProgressText, 'アップロード完了！');

      setTimeout(function () {
        core.hideElement(uploadProgressContainer);
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = uploadButtonLabel;

        var statusMessage = '';
        var isError = false;
        var responseData = response.data || {};
        if (response.status === 'ok') {
          statusMessage = responseData.message || 'ファイルのアップロードが完了しました。';
          clearFiles();
          refreshRemoteFiles();
        } else if (response.status === 'error') {
          isError = true;
          var errorDetails = response.error || responseData.message || 'アップロード中にエラーが発生しました。';
          if (Array.isArray(responseData.files) && responseData.files.length > 0) {
            errorDetails += '（対象ファイル: ' + responseData.files.join(', ') + '）';
          }
          statusMessage = errorDetails;
        } else {
          statusMessage = 'ファイルのアップロードが完了しました。';
          clearFiles();
          refreshRemoteFiles();
        }

        if (statusMessage) {
          showStatusMessage(statusMessage, isError);
        }
      }, 1000);
    }

    function uploadFiles() {
      var filesArray = getFiles();
      if (!validateFiles(filesArray)) {
        return;
      }

      var formData = buildUploadFormData(filesArray);
      showUploadProgressStart();

      var xhr = new window.XMLHttpRequest();
      xhr.open('POST', `/group_upload/${roomId}/${roomPassword}`, true);
      if (csrfToken) {
        xhr.setRequestHeader('X-CSRF-Token', csrfToken);
      }

      xhr.upload.addEventListener('progress', function (evt) {
        if (evt.lengthComputable) {
          var percentComplete = evt.loaded / evt.total;
          core.setProgressScale(uploadProgressBar, percentComplete);
          core.setElementText(uploadProgressText, `アップロード中... ${Math.round(percentComplete * 100)}%`);
        }
      }, false);

      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          var response = parseJsonResponse(xhr.responseText, 'group upload response');
          if (!isUploadResponsePayload(response)) {
            showUploadError(xhr);
            return;
          }
          try {
            handleUploadResponse(response);
          } catch (error) {
            showUploadError(xhr);
          }
          return;
        }
        showUploadError(xhr);
      };

      xhr.onerror = function () {
        showUploadError(xhr);
      };

      xhr.send(formData);
    }

    return {
      bindUpload: function () {
        uploadBtn.addEventListener('click', uploadFiles);
      }
    };
  }

  modules.uploadSubmit = {
    createUploadSubmitter: createUploadSubmitter
  };
})(window);
