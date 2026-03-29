(function (window) {
  window.GroupRoomModules = window.GroupRoomModules || {};
  var modules = window.GroupRoomModules;

  function createUploadQueue(options) {
    var uploadArea = options.uploadArea;
    var fileInput = options.fileInput;
    var fileList = options.fileList;
    var icons = options.icons;
    var setUploadIcon = options.setUploadIcon;

    var filesArray = [];

    function handleFiles(files) {
      var MAX_FILES = 10;
      var totalFiles = filesArray.length + files.length;
      if (totalFiles > MAX_FILES) {
        alert(`ファイル数は最大${MAX_FILES}個までです（現在: ${filesArray.length}個、追加しようとしているファイル: ${files.length}個）`);
        return;
      }

      var MAX_TOTAL_SIZE = 500 * 1024 * 1024;
      var currentSize = 0;
      var newFilesSize = 0;

      filesArray.forEach(function (file) {
        currentSize += file.size;
      });

      for (var i = 0; i < files.length; i += 1) {
        newFilesSize += files[i].size;
      }

      var totalSize = currentSize + newFilesSize;
      if (totalSize > MAX_TOTAL_SIZE) {
        var totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);
        alert(`ファイルの合計サイズは500MBまでです（現在の合計: ${totalSizeMB}MB）`);
        return;
      }

      fileList.show();

      for (var index = 0; index < files.length; index += 1) {
        filesArray.push(files[index]);
        var fileItem = $('<div class="modern-file-item"></div>');
        var fileName = $('<div class="modern-file-name"></div>');
        var fileNameText = $('<span class="modern-file-name-text"></span>').text(files[index].name);
        fileName.html(icons.file).append(fileNameText);

        var actions = $('<div class="modern-file-actions"></div>');
        var deleteBtn = $('<button class="modern-file-action-btn delete"></button>')
          .html(icons.trash)
          .attr('aria-label', '削除')
          .attr('title', '削除');

        deleteBtn.on('click', (function (deleteIndex) {
          return function () {
            filesArray.splice(deleteIndex, 1);
            $(this).closest('.modern-file-item').remove();
            if (filesArray.length === 0) {
              fileList.hide();
              setUploadIcon('cloud');
            }
          };
        })(filesArray.length - 1));

        actions.append(deleteBtn);
        fileItem.append(fileName).append(actions);
        fileList.append(fileItem);
      }

      setUploadIcon('check');
    }

    function bindFileSelection() {
      uploadArea.on('dragover', function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.addClass('dragover');
      });

      uploadArea.on('dragleave', function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.removeClass('dragover');
      });

      uploadArea.on('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.removeClass('dragover');
        var files = e.originalEvent.dataTransfer.files;
        handleFiles(files);
      });

      uploadArea.on('click', function (e) {
        if (e.target.tagName !== 'BUTTON') {
          fileInput[0].click();
        }
      });

      $('#uploadFileBtn').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        fileInput[0].click();
      });

      fileInput.on('change', function () {
        var files = fileInput[0].files;
        handleFiles(files);
      });
    }

    function getFiles() {
      return filesArray;
    }

    function clearFiles() {
      filesArray = [];
      fileList.empty().hide();
      setUploadIcon('cloud');
    }

    return {
      bindFileSelection: bindFileSelection,
      getFiles: getFiles,
      clearFiles: clearFiles
    };
  }

  modules.uploadQueue = {
    createUploadQueue: createUploadQueue
  };
})(window);
