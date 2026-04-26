(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');

  function createUploadQueue(options) {
    var uploadArea = options.uploadArea;
    var fileInput = options.fileInput;
    var fileList = options.fileList;
    var icons = options.icons;
    var setUploadIcon = options.setUploadIcon;
    var validation = appNamespace.api.getShared('uploadValidation');
    if (!validation) {
      throw new Error('Shared upload validation is not initialized.');
    }
    var limits = validation.normalizeLimits(options.limits || {});
    var filePickerButton = document.getElementById('uploadFileBtn');

    var filesArray = [];

    function notify(message) {
      if (typeof window.showAlertModal === 'function') {
        window.showAlertModal(message);
        return;
      }
      window.alert(message);
    }

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
      var result = validation.validateSelection(files, limits, {
        existingFilesCount: filesArray.length,
        existingTotalSize: validation.calculateTotalSize(filesArray),
        checkFileName: true
      });

      if (!result.ok) {
        if (result.reason === 'max_files') {
          notify(`ファイル数は最大${limits.maxFiles}個までです。現在${filesArray.length}個、追加しようとしているファイルは${result.selectedFilesCount}個です。`);
        } else if (result.reason === 'max_total_size') {
          notify(`ファイルの合計サイズは${limits.maxTotalSizeMB}MBまでです。現在の合計は${result.totalSizeMB}MBです。`);
        } else if (result.reason === 'invalid_filename') {
          notify('不正なファイル名が含まれています。ファイル名を変更して再度お試しください。');
        }
        return;
      }

      var selectedFiles = validation.toArray(files);
      for (var index = 0; index < selectedFiles.length; index += 1) {
        filesArray.push(selectedFiles[index]);
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
