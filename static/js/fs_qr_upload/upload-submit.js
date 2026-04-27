(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

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
    var uploadButtonLabel = options.uploadButtonLabel || 'アップロード開始';
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
        showFormError('ファイルと共有用IDを確認してください。');
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
          showFormError(`ファイル数は最大${limits.maxFiles}個までです。`);
        } else if (result.reason === 'max_total_size') {
          showFormError(`ファイルの合計サイズは${limits.maxTotalSizeMB}MBまでです。現在の合計は${result.totalSizeMB}MBです。`);
        } else if (result.reason === 'invalid_filename') {
          showFormError('不正なファイル名が含まれています。ファイル名を変更して再度お試しください。');
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
          spinner.setSpinnerText('キャンセルしています...');
          spinner.setSpinnerDetail('暗号化中の場合は、現在の処理が終わり次第キャンセルします。');
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
          startUploadBtn.textContent = '処理中...';
        }

        var files = fileInput.files;
        var id = getCurrentId();

        if (!validateBeforeSubmit(files, id)) {
          return;
        }

        try {
          var fileNames = Array.from(files).map(function (file) { return file.name; });
          spinner.setSpinnerEyebrow('暗号化');
          spinner.setSpinnerText('アップロード準備中...');
          spinner.setSpinnerDetail(`対象ファイル: ${fileNames[0]}${fileNames.length > 1 ? ` ほか${fileNames.length - 1}件` : ''}`);
          spinner.setProgressScale(0);
          spinner.setUploadProgressScale(0);
          await new Promise(function (resolve) {
            setTimeout(resolve, 1000);
          });

          if (cancelRequested) {
            throw new Error('アップロードをキャンセルしました。');
          }

          spinner.setSpinnerText('暗号化中...');
          var encryptedBlob = await encryptionService.encryptAndZipFilesWithProgress(files, id);
          if (cancelRequested) {
            throw new Error('アップロードをキャンセルしました。');
          }

          spinner.setSpinnerEyebrow('アップロード');
          spinner.setSpinnerText('送信中...');
          spinner.setSpinnerDetail(`送信対象: ${fileNames.length}件`);
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
              spinner.setSpinnerText(`送信中... ${Math.round(uploadProgress * 100)}%`);
            }
          };

          xhr.onload = function () {
            if (xhr.status === 200) {
              var result = parseJsonResponse(xhr.responseText, 'fsqr upload response');
              if (!isObjectPayload(result)) {
                showFormError('アップロードは完了しましたが、レスポンス形式が不正です。画面を再読み込みして確認してください。');
                spinner.hideSpinner();
              } else if (
                result.status === 'ok'
                && result.data
                && typeof result.data.redirect_url === 'string'
                && result.data.redirect_url
              ) {
                window.location.href = result.data.redirect_url;
              } else {
                showFormError('アップロードは完了しましたが、遷移先を取得できませんでした。画面を再読み込みして確認してください。');
                spinner.hideSpinner();
              }
            } else {
              var errorResult = parseJsonResponse(xhr.responseText, 'fsqr upload error');
              if (isObjectPayload(errorResult) && typeof errorResult.error === 'string' && errorResult.error) {
                showFormError(errorResult.error);
              } else {
                showFormError('アップロードに失敗しました。時間をおいて再度お試しください。');
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
            showFormError('送信中にエラーが発生しました。通信状態を確認して再度お試しください。');
            spinner.hideSpinner();
            if (startUploadBtn) {
              startUploadBtn.disabled = false;
              startUploadBtn.innerHTML = uploadButtonLabel;
            }
            spinner.stopIconSwitching();
            activeXhr = null;
          };

          xhr.onabort = function () {
            showFormError('アップロードをキャンセルしました。');
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
          showFormError(`処理中にエラーが発生しました。${error.message}`);
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
