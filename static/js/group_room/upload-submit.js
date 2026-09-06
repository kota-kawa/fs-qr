(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function') {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  function createUploadSubmitter(options) {
    var uploadBtn = options.uploadBtn;
    var uploadStatusMessage = options.uploadStatusMessage;
    var uploadButtonLabel = options.uploadButtonLabel;
    var roomId = options.roomId;
    var csrfToken = options.csrfToken;
    var core = options.core;
    var getFiles = options.getFiles;
    var clearFiles = options.clearFiles;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var refreshRemoteFiles = typeof options.refreshRemoteFiles === 'function'
      ? options.refreshRemoteFiles
      : function () {};
    var getRoomUsage = typeof options.getRoomUsage === 'function'
      ? options.getRoomUsage
      : function () { return { fileCount: 0, totalSizeBytes: 0 }; };
    var validation = appNamespace.api.getShared('uploadValidation');
    if (!validation) {
      throw new Error('Shared upload validation is not initialized.');
    }
    var limits = validation.normalizeLimits(options.limits || {});
    var uploadProgressContainer = document.getElementById('uploadProgressContainer');
    var uploadProgressBar = document.getElementById('uploadProgressBar');
    var uploadProgressText = document.getElementById('uploadProgressText');
    var sharedSpinner = appNamespace.api.getShared('progressSpinner');
    var uploadProgressController = sharedSpinner
      ? sharedSpinner.createProgressSpinner({
        root: uploadProgressContainer,
        animationContainer: uploadProgressContainer,
        text: uploadProgressText,
        bars: { primary: uploadProgressBar }
      })
      : null;

    function notify(message) {
      if (typeof window.showAlertModal === 'function') {
        window.showAlertModal(message);
        return;
      }
      window.alert(message);
    }

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
        notify(translate('upload.no_files', 'No files to upload.'));
        return false;
      }

      var usage = getRoomUsage() || {};
      var existingFilesCount = Number(usage.fileCount) || 0;
      var existingTotalSize = Number(usage.totalSizeBytes) || 0;

      var result = validation.validateSelection(filesArray, limits, {
        checkFileName: true,
        existingFilesCount: existingFilesCount,
        existingTotalSize: existingTotalSize
      });
      if (!result.ok) {
        notify(validation.describeFailure(result, {
          scope: 'group-submit',
          existingFilesCount: existingFilesCount
        }));
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

    function scrollProgressIntoCenter() {
      if (!uploadProgressContainer || typeof uploadProgressContainer.scrollIntoView !== 'function') {
        return;
      }
      window.requestAnimationFrame(function () {
        try {
          uploadProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch (error) {
          uploadProgressContainer.scrollIntoView(true);
        }
      });
    }

    function showUploadProgressStart() {
      if (uploadProgressController) {
        uploadProgressController.show();
        uploadProgressController.resetProgress();
        uploadProgressController.setText(translate('upload.uploading', 'Uploading...'));
        uploadProgressController.scrollIntoCenter();
      } else {
        core.showElement(uploadProgressContainer);
        core.setProgressScale(uploadProgressBar, 0);
        core.setElementText(uploadProgressText, translate('upload.uploading', 'Uploading...'));
      }
      resetStatusMessage();
      uploadBtn.disabled = true;
      uploadBtn.textContent = translate('upload.uploading', 'Uploading...');
      if (!uploadProgressController) {
        scrollProgressIntoCenter();
      }
    }

    function showUploadError(xhr) {
      if (uploadProgressController) {
        uploadProgressController.hide();
      } else {
        core.hideElement(uploadProgressContainer);
      }
      uploadBtn.disabled = false;
      uploadBtn.innerHTML = uploadButtonLabel;

      var errorMessage = translate('upload.error_upload', 'An error occurred during upload.');
      if (xhr && xhr.responseText) {
        var responseJson = parseJsonResponse(xhr.responseText, 'group upload error');
        if (responseJson && typeof responseJson.error === 'string' && responseJson.error) {
          errorMessage = responseJson.error;
        }
      }

      showStatusMessage(errorMessage, true);
    }

    function handleUploadResponse(response) {
      if (uploadProgressController) {
        uploadProgressController.setProgress(1);
        uploadProgressController.setText(translate('upload.complete', 'Upload complete!'));
      } else {
        core.setProgressScale(uploadProgressBar, 1);
        core.setElementText(uploadProgressText, translate('upload.complete', 'Upload complete!'));
      }

      setTimeout(function () {
        if (uploadProgressController) {
          uploadProgressController.hide();
        } else {
          core.hideElement(uploadProgressContainer);
        }
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = uploadButtonLabel;

        var statusMessage = '';
        var isError = false;
        var responseData = response.data || {};
        if (response.status === 'ok') {
          statusMessage = responseData.message || translate('upload.complete_message', 'File upload completed.');
          clearFiles();
          refreshRemoteFiles();
        } else if (response.status === 'error') {
          isError = true;
          var errorDetails = response.error || responseData.message || translate('upload.error_upload', 'An error occurred during upload.');
          if (Array.isArray(responseData.files) && responseData.files.length > 0) {
            errorDetails += translate('upload.error_file_list', '(Files: {files})').replace('{files}', responseData.files.join(', '));
          }
          statusMessage = errorDetails;
        } else {
          statusMessage = translate('upload.complete_message', 'File upload completed.');
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
      xhr.open('POST', `/group_upload/${roomId}`, true);
      if (csrfToken) {
        xhr.setRequestHeader('X-CSRF-Token', csrfToken);
      }

      xhr.upload.addEventListener('progress', function (evt) {
        if (evt.lengthComputable) {
          var percentComplete = evt.loaded / evt.total;
          var progressText = translate('upload.uploading_progress', 'Uploading... {percent}%').replace('{percent}', String(Math.round(percentComplete * 100)));
          if (uploadProgressController) {
            uploadProgressController.setProgress(percentComplete);
            uploadProgressController.setText(progressText);
          } else {
            core.setProgressScale(uploadProgressBar, percentComplete);
            core.setElementText(uploadProgressText, progressText);
          }
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
