(function (window) {
  window.GroupRoomModules = window.GroupRoomModules || {};
  var modules = window.GroupRoomModules;

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
    var limits = options.limits || {};
    var uploadProgressContainer = document.getElementById('uploadProgressContainer');
    var uploadProgressBar = document.getElementById('uploadProgressBar');
    var uploadProgressText = document.getElementById('uploadProgressText');
    var parsedMaxFiles = Number(limits.maxFiles);
    var parsedMaxTotalSizeBytes = Number(limits.maxTotalSizeBytes);
    var parsedMaxTotalSizeMB = Number(limits.maxTotalSizeMB);
    var maxFiles = Number.isFinite(parsedMaxFiles) && parsedMaxFiles > 0 ? parsedMaxFiles : 1;
    var maxTotalSizeBytes = Number.isFinite(parsedMaxTotalSizeBytes) && parsedMaxTotalSizeBytes > 0
      ? parsedMaxTotalSizeBytes
      : 1;
    var maxTotalSizeMB = Number.isFinite(parsedMaxTotalSizeMB) && parsedMaxTotalSizeMB > 0
      ? parsedMaxTotalSizeMB
      : Math.max(1, Math.ceil(maxTotalSizeBytes / (1024 * 1024)));

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

      if (filesArray.length > maxFiles) {
        alert(`ファイル数は最大${maxFiles}個までです`);
        return false;
      }

      var totalSize = 0;
      filesArray.forEach(function (file) {
        totalSize += file.size;
      });

      if (totalSize > maxTotalSizeBytes) {
        var sizeMB = (totalSize / (1024 * 1024)).toFixed(2);
        alert(`ファイルの合計サイズは${maxTotalSizeMB}MBまでです（現在: ${sizeMB}MB）`);
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
        try {
          var responseJson = JSON.parse(xhr.responseText);
          if (responseJson.error) {
            errorMessage = responseJson.error;
          }
        } catch (error) {
          // Keep default message when JSON parsing fails.
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
        if (response.status === 'success') {
          statusMessage = 'ファイルのアップロードが完了しました。';
          clearFiles();
        } else if (response.status === 'error') {
          isError = true;
          var errorDetails = response.message || 'アップロード中にエラーが発生しました。';
          if (Array.isArray(response.files) && response.files.length > 0) {
            errorDetails += '（対象ファイル: ' + response.files.join(', ') + '）';
          }
          statusMessage = errorDetails;
        } else {
          statusMessage = 'ファイルのアップロードが完了しました。';
          clearFiles();
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
          try {
            var response = JSON.parse(xhr.responseText);
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
