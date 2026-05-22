(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function translate(key, fallback) {
    if (window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function') {
      return window.FSQR_I18N.t(key, fallback);
    }
    return fallback || key;
  }

  function createUploadSubmitter(options) {
    var uploadForm = options.uploadForm;
    var fileInput = options.fileInput;
    var startUploadBtn = options.startUploadBtn;
    var cancelUploadBtn = options.cancelUploadBtn;
    var retentionSelect = options.retentionSelect;
    var getCurrentId = options.getCurrentId;
    var clearFormError = options.clearFormError;
    var showFormError = options.showFormError;
    var csrfToken = options.csrfToken;
    var spinner = options.spinner;
    var encryptionService = options.encryptionService;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var uploadButtonLabel = options.uploadButtonLabel || translate('upload.start', 'Start upload');
    var validation = appNamespace.api.getShared('uploadValidation');
    if (!validation) {
      throw new Error('Shared upload validation is not initialized.');
    }
    var limits = validation.normalizeLimits(options.limits || {});
    var core = modules.core;
    var activeXhr = null;
    var cancelRequested = false;

    function parseJsonResponse(rawText, label) {
      return core.safeParseJson(rawText, logger, label);
    }

    function isObjectPayload(payload) {
      if (!core.isPlainObject(payload)) {
        return false;
      }
      if (payload.status !== undefined && payload.status !== 'ok' && payload.status !== 'error') {
        return false;
      }
      if (payload.data !== undefined && !core.isPlainObject(payload.data)) {
        return false;
      }
      if (payload.error !== undefined && payload.error !== null && typeof payload.error !== 'string') {
        return false;
      }
      return true;
    }

    function validateBeforeSubmit(files, id) {
      if (!(files.length > 0 && id.length > 0)) {
        showFormError(translate('upload.file_id_required', 'Please check the file and sharing ID.'));
        if (startUploadBtn) {
          startUploadBtn.disabled = false;
          startUploadBtn.innerHTML = uploadButtonLabel;
        }
        spinner.hideSpinner();
        spinner.stopIconSwitching();
        return false;
      }

      var result = validation.validateSelection(files, limits, { checkFileName: true });
      if (!result.ok) {
        if (result.reason === 'max_files') {
          showFormError(translate('upload.error_max_files', 'You can upload a maximum of {max} files.').replace('{max}', String(limits.maxFiles)));
        } else if (result.reason === 'max_total_size') {
          showFormError(translate('upload.error_max_size', 'The total file size limit is {max} MB. The current total is {current} MB.').replace('{max}', String(limits.maxTotalSizeMB)).replace('{current}', String(result.totalSizeMB)));
        } else if (result.reason === 'invalid_filename') {
          showFormError(translate('upload.invalid_filename', 'An invalid file name is included. Rename the file and try again.'));
        }
        if (startUploadBtn) {
          startUploadBtn.disabled = false;
          startUploadBtn.innerHTML = uploadButtonLabel;
        }
        spinner.hideSpinner();
        spinner.stopIconSwitching();
        return false;
      }

      return true;
    }

    function buildUploadFormData(files, encryptedBlob, id) {
      var formData = new FormData();
      if (files.length === 1) {
        var encryptedFile = new File([encryptedBlob], `${files[0].name}.enc`, { type: 'application/octet-stream' });
        formData.append('upfile', encryptedFile);
        formData.append('file_type', 'single');
      } else {
        var zipFile = new File([encryptedBlob], 'encrypted_files.zip', { type: 'application/zip' });
        formData.append('upfile', zipFile);
        formData.append('file_type', 'multiple');
      }
      formData.append('name', id);
      formData.append('original_filename', files[0].name);
      formData.append('retention_days', retentionSelect.value);
      return formData;
    }

    function bindUpload() {
      if (cancelUploadBtn) {
        cancelUploadBtn.addEventListener('click', function () {
          cancelRequested = true;
          if (activeXhr) {
            activeXhr.abort();
          }
          spinner.setSpinnerText(translate('upload.canceling', 'Canceling...'));
          spinner.setSpinnerDetail(translate('upload.cancel_detail', 'If encrypting, cancellation will happen after the current step completes.'));
        });
      }

      uploadForm.addEventListener('submit', async function (event) {
        event.preventDefault();
        clearFormError();
        cancelRequested = false;

        if (!uploadForm.reportValidity()) {
          return;
        }

        spinner.showSpinner();
        spinner.startEncryptionAnimation();
        if (startUploadBtn) {
          startUploadBtn.disabled = true;
          startUploadBtn.textContent = translate('common.processing', 'Processing...');
        }

        var files = fileInput.files;
        var id = getCurrentId();

        if (!validateBeforeSubmit(files, id)) {
          return;
        }

        try {
          var fileNames = Array.from(files).map(function (file) { return file.name; });
          spinner.setSpinnerEyebrow(translate('upload.encryption', 'Encryption'));
          spinner.setSpinnerText(translate('upload.preparing_start', 'Preparing upload...'));
          spinner.setSpinnerDetail(translate('upload.target_file', 'Target file: {name}').replace('{name}', fileNames[0]) + (fileNames.length > 1 ? translate('upload.target_file_more', ' and {n} more').replace('{n}', String(fileNames.length - 1)) : ''));
          spinner.setProgressScale(0);
          spinner.setUploadProgressScale(0);
          await new Promise(function (resolve) {
            setTimeout(resolve, 1000);
          });

          if (cancelRequested) {
            throw new Error(translate('upload.canceled', 'Upload canceled.'));
          }

          spinner.setSpinnerText(translate('upload.encrypting', 'Encrypting...'));
          var encryptedBlob = await encryptionService.encryptAndZipFilesWithProgress(files);
          var shareKey = typeof encryptionService.getLastEncryptionKey === 'function'
            ? encryptionService.getLastEncryptionKey()
            : '';
          if (cancelRequested) {
            throw new Error(translate('upload.canceled', 'Upload canceled.'));
          }

          spinner.setSpinnerEyebrow(translate('upload.upload', 'Upload'));
          spinner.setSpinnerText(translate('upload.sending', 'Sending...'));
          spinner.setSpinnerDetail(translate('upload.sending_files', 'Sending {n} file(s)').replace('{n}', String(fileNames.length)));
          spinner.startUploadAnimation();

          var formData = buildUploadFormData(files, encryptedBlob, id);
          var xhr = new XMLHttpRequest();
          activeXhr = xhr;
          xhr.open('POST', '/upload', true);
          if (csrfToken) {
            xhr.setRequestHeader('X-CSRF-Token', csrfToken);
          }
          xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
          xhr.setRequestHeader('Accept', 'application/json');

          xhr.upload.onprogress = function (progressEvent) {
            if (progressEvent.lengthComputable) {
              var uploadProgress = progressEvent.loaded / progressEvent.total;
              spinner.setUploadProgressScale(uploadProgress);
              spinner.setSpinnerText(translate('upload.sending_progress', 'Sending... {percent}%').replace('{percent}', String(Math.round(uploadProgress * 100))));
            }
          };

          xhr.onload = function () {
            if (xhr.status === 200) {
              var result = parseJsonResponse(xhr.responseText, 'fsqr upload response');
              if (!isObjectPayload(result)) {
                showFormError(translate('upload.error_response_format', 'Upload completed, but the response format is invalid. Please reload the page.'));
                spinner.hideSpinner();
              } else if (
                result.status === 'ok'
                && result.data
                && typeof result.data.redirect_url === 'string'
                && result.data.redirect_url
              ) {
                window.location.href = result.data.redirect_url
                  + (shareKey ? `#key=${encodeURIComponent(shareKey)}` : '');
              } else {
                showFormError(translate('upload.error_no_redirect', 'Upload completed, but the redirect URL could not be retrieved. Please reload the page.'));
                spinner.hideSpinner();
              }
            } else {
              var errorResult = parseJsonResponse(xhr.responseText, 'fsqr upload error');
              if (isObjectPayload(errorResult) && typeof errorResult.error === 'string' && errorResult.error) {
                showFormError(errorResult.error);
              } else {
                showFormError(translate('upload.error_failed', 'Upload failed. Please try again later.'));
              }
              spinner.hideSpinner();
            }
            if (startUploadBtn) {
              startUploadBtn.disabled = false;
              startUploadBtn.innerHTML = uploadButtonLabel;
            }
            spinner.stopIconSwitching();
            activeXhr = null;
          };

          xhr.onerror = function () {
            showFormError(translate('upload.send_error', 'An error occurred while sending. Check your connection and try again.'));
            spinner.hideSpinner();
            if (startUploadBtn) {
              startUploadBtn.disabled = false;
              startUploadBtn.innerHTML = uploadButtonLabel;
            }
            spinner.stopIconSwitching();
            activeXhr = null;
          };

          xhr.onabort = function () {
            showFormError(translate('upload.canceled', 'Upload canceled.'));
            spinner.hideSpinner();
            if (startUploadBtn) {
              startUploadBtn.disabled = false;
              startUploadBtn.innerHTML = uploadButtonLabel;
            }
            spinner.stopIconSwitching();
            activeXhr = null;
          };

          xhr.send(formData);
        } catch (error) {
          showFormError(translate('upload.error_processing', 'An error occurred during processing. {message}').replace('{message}', error.message));
          spinner.hideSpinner();
          if (startUploadBtn) {
            startUploadBtn.disabled = false;
            startUploadBtn.innerHTML = uploadButtonLabel;
          }
          spinner.stopIconSwitching();
        }
      });
    }

    return {
      bindUpload: bindUpload,
      getUploadButtonLabel: function () {
        return uploadButtonLabel;
      }
    };
  }

  modules.uploadSubmit = {
    createUploadSubmitter: createUploadSubmitter
  };
})(window);
