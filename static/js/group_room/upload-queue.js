(function (window) {
  window.GroupRoomModules = window.GroupRoomModules || {};
  var modules = window.GroupRoomModules;

  function createUploadQueue(options) {
    var uploadArea = options.uploadArea;
    var fileInput = options.fileInput;
    var fileList = options.fileList;
    var icons = options.icons;
    var setUploadIcon = options.setUploadIcon;
    var filePickerButton = document.getElementById('uploadFileBtn');

    var filesArray = [];

    function renderFileList() {
      fileList.innerHTML = '';
      if (filesArray.length === 0) {
        fileList.style.display = 'none';
        setUploadIcon('cloud');
        return;
      }

      fileList.style.display = 'block';
      filesArray.forEach(function (file, index) {
        var fileItem = document.createElement('div');
        fileItem.className = 'modern-file-item';

        var fileName = document.createElement('div');
        fileName.className = 'modern-file-name';
        fileName.innerHTML = `${icons.file}<span class="modern-file-name-text"></span>`;
        var fileNameText = fileName.querySelector('.modern-file-name-text');
        if (fileNameText) {
          fileNameText.textContent = file.name;
        }

        var actions = document.createElement('div');
        actions.className = 'modern-file-actions';

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'modern-file-action-btn delete';
        deleteBtn.type = 'button';
        deleteBtn.innerHTML = icons.trash;
        deleteBtn.setAttribute('aria-label', '削除');
        deleteBtn.setAttribute('title', '削除');
        deleteBtn.addEventListener('click', function () {
          filesArray.splice(index, 1);
          renderFileList();
        });

        actions.appendChild(deleteBtn);
        fileItem.appendChild(fileName);
        fileItem.appendChild(actions);
        fileList.appendChild(fileItem);
      });

      setUploadIcon('check');
    }

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

      for (var index = 0; index < files.length; index += 1) {
        filesArray.push(files[index]);
      }
      renderFileList();
    }

    function bindFileSelection() {
      uploadArea.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.add('dragover');
      });

      uploadArea.addEventListener('dragleave', function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.remove('dragover');
      });

      uploadArea.addEventListener('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.remove('dragover');
        var files = e.dataTransfer.files;
        handleFiles(files);
      });

      uploadArea.addEventListener('click', function (e) {
        if (e.target.tagName !== 'BUTTON') {
          fileInput.click();
        }
      });

      if (filePickerButton) {
        filePickerButton.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          fileInput.click();
        });
      }

      fileInput.addEventListener('change', function () {
        var files = fileInput.files;
        handleFiles(files);
      });
    }

    function getFiles() {
      return filesArray;
    }

    function clearFiles() {
      filesArray = [];
      renderFileList();
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
