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
    var getFiles = options.getFiles;
    var clearFiles = options.clearFiles;

    function validateFiles(filesArray) {
      if (filesArray.length === 0) {
        alert('アップロードするファイルがありません。');
        return false;
      }

      var MAX_FILES = 10;
      var MAX_TOTAL_SIZE = 500 * 1024 * 1024;

      if (filesArray.length > MAX_FILES) {
        alert(`ファイル数は最大${MAX_FILES}個までです`);
        return false;
      }

      var totalSize = 0;
      filesArray.forEach(function (file) {
        totalSize += file.size;
      });

      if (totalSize > MAX_TOTAL_SIZE) {
        var sizeMB = (totalSize / (1024 * 1024)).toFixed(2);
        alert(`ファイルの合計サイズは500MBまでです（現在: ${sizeMB}MB）`);
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
      $('#uploadProgressContainer').show();
      $('#uploadProgressBar').css('transform', 'scaleX(0)');
      $('#uploadProgressText').text('アップロード中...');
      uploadStatusMessage.removeClass('is-error').hide().text('');
      uploadBtn.prop('disabled', true).text('アップロード中...');
    }

    function showUploadError(xhr) {
      $('#uploadProgressContainer').hide();
      uploadBtn.prop('disabled', false).html(uploadButtonLabel);

      var errorMessage = 'アップロード中にエラーが発生しました。';
      if (xhr.responseJSON && xhr.responseJSON.error) {
        errorMessage = xhr.responseJSON.error;
      }

      uploadStatusMessage
        .addClass('is-error')
        .text(errorMessage)
        .fadeIn();
    }

    function handleUploadResponse(response) {
      $('#uploadProgressBar').css('transform', 'scaleX(1)');
      $('#uploadProgressText').text('アップロード完了！');

      setTimeout(function () {
        $('#uploadProgressContainer').hide();
        uploadBtn.prop('disabled', false).html(uploadButtonLabel);

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
          uploadStatusMessage
            .toggleClass('is-error', isError)
            .text(statusMessage)
            .fadeIn();
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

      $.ajax({
        url: `/group_upload/${roomId}/${roomPassword}`,
        type: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
        data: formData,
        processData: false,
        contentType: false,
        xhr: function () {
          var xhr = new window.XMLHttpRequest();
          xhr.upload.addEventListener('progress', function (evt) {
            if (evt.lengthComputable) {
              var percentComplete = evt.loaded / evt.total;
              $('#uploadProgressBar').css('transform', `scaleX(${percentComplete})`);
              $('#uploadProgressText').text(`アップロード中... ${Math.round(percentComplete * 100)}%`);
            }
          }, false);
          return xhr;
        },
        success: handleUploadResponse,
        error: showUploadError
      });
    }

    return {
      bindUpload: function () {
        uploadBtn.on('click', uploadFiles);
      }
    };
  }

  modules.uploadSubmit = {
    createUploadSubmitter: createUploadSubmitter
  };
})(window);
