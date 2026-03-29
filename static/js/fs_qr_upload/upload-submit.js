(function (window) {
  window.FsQrUploadModules = window.FsQrUploadModules || {};
  var modules = window.FsQrUploadModules;

  function createUploadSubmitter(options) {
    var uploadForm = options.uploadForm;
    var fileInput = options.fileInput;
    var retentionSelect = options.retentionSelect;
    var getCurrentId = options.getCurrentId;
    var clearFormError = options.clearFormError;
    var showFormError = options.showFormError;
    var csrfToken = options.csrfToken;
    var spinner = options.spinner;
    var encryptionService = options.encryptionService;

    function validateBeforeSubmit(files, id) {
      if (!(files.length > 0 && id.length > 0)) {
        showFormError('ファイルと共有用IDを確認してください。');
        spinner.hideSpinner();
        spinner.stopIconSwitching();
        return false;
      }

      var MAX_FILES = 10;
      var MAX_TOTAL_SIZE = 500 * 1024 * 1024;

      if (files.length > MAX_FILES) {
        showFormError(`ファイル数は最大${MAX_FILES}個までです。`);
        spinner.hideSpinner();
        spinner.stopIconSwitching();
        return false;
      }

      var totalSize = 0;
      Array.from(files).forEach(function (file) {
        totalSize += file.size;
      });

      if (totalSize > MAX_TOTAL_SIZE) {
        var sizeMB = (totalSize / (1024 * 1024)).toFixed(2);
        showFormError(`ファイルの合計サイズは500MBまでです。現在の合計は ${sizeMB}MB です。`);
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
      uploadForm.addEventListener('submit', async function (event) {
        event.preventDefault();
        clearFormError();

        if (!uploadForm.reportValidity()) {
          return;
        }

        spinner.showSpinner();
        spinner.startEncryptionAnimation();

        var files = fileInput.files;
        var id = getCurrentId();

        if (!validateBeforeSubmit(files, id)) {
          return;
        }

        try {
          spinner.setSpinnerText('アップロード準備中...');
          await new Promise(function (resolve) {
            setTimeout(resolve, 1000);
          });

          spinner.setSpinnerText('暗号化中...');
          var encryptedBlob = await encryptionService.encryptAndZipFilesWithProgress(files, id);

          spinner.setSpinnerText('送信中...');
          spinner.startUploadAnimation();

          var formData = buildUploadFormData(files, encryptedBlob, id);
          var xhr = new XMLHttpRequest();
          xhr.open('POST', '/upload', true);
          if (csrfToken) {
            xhr.setRequestHeader('X-CSRF-Token', csrfToken);
          }

          xhr.upload.onprogress = function (progressEvent) {
            if (progressEvent.lengthComputable) {
              var uploadProgress = (progressEvent.loaded / progressEvent.total) * 50;
              var totalProgress = 50 + uploadProgress;
              spinner.setProgressScale(totalProgress / 100);
            }
          };

          xhr.onload = function () {
            if (xhr.status === 200) {
              var result = JSON.parse(xhr.responseText);
              if (result.redirect_url) {
                window.location.href = result.redirect_url;
              } else {
                showFormError('アップロードは完了しましたが、遷移先を取得できませんでした。画面を再読み込みして確認してください。');
                spinner.hideSpinner();
              }
            } else {
              try {
                var errorResult = JSON.parse(xhr.responseText);
                if (errorResult.error) {
                  showFormError(errorResult.error);
                } else {
                  showFormError('アップロードに失敗しました。時間をおいて再度お試しください。');
                }
              } catch (parseError) {
                showFormError('アップロードに失敗しました。時間をおいて再度お試しください。');
              }
              spinner.hideSpinner();
            }
            spinner.stopIconSwitching();
          };

          xhr.onerror = function () {
            showFormError('送信中にエラーが発生しました。通信状態を確認して再度お試しください。');
            spinner.hideSpinner();
            spinner.stopIconSwitching();
          };

          xhr.send(formData);
        } catch (error) {
          showFormError(`処理中にエラーが発生しました。${error.message}`);
          spinner.hideSpinner();
          spinner.stopIconSwitching();
        }
      });
    }

    return {
      bindUpload: bindUpload
    };
  }

  modules.uploadSubmit = {
    createUploadSubmitter: createUploadSubmitter
  };
})(window);
