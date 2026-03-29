(function (window) {
  window.FsQrUploadModules = window.FsQrUploadModules || {};
  var modules = window.FsQrUploadModules;

  function createFileSelectionController(options) {
    var uploadArea = options.uploadArea;
    var fileInput = options.fileInput;
    var fileListDisplay = options.fileListDisplay;
    var icons = options.icons;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var clearFormError = options.clearFormError;
    var showFormError = options.showFormError;
    var setUploadIcon = options.setUploadIcon;
    var setFileInputFiles = options.setFileInputFiles;
    var validation = window.SharedUploadValidation;
    var limits = validation.normalizeLimits(options.limits || {});

    function validateFiles(files) {
      var result = validation.validateSelection(files, limits, { checkFileName: true });
      if (!result.ok) {
        if (result.reason === 'max_files') {
          showFormError(`ファイル数は最大${limits.maxFiles}個までです。不要なファイルを外して再度お試しください。`);
        } else if (result.reason === 'max_total_size') {
          showFormError(`ファイルの合計サイズは${limits.maxTotalSizeMB}MBまでです。現在の合計は ${result.totalSizeMB}MB です。`);
        } else if (result.reason === 'invalid_filename') {
          showFormError('不正なファイル名が含まれています。ファイル名を変更して再度お試しください。');
        }
        return false;
      }

      return true;
    }

    function renderFileList(files) {
      fileListDisplay.innerHTML = '';
      fileListDisplay.style.display = 'block';

      Array.from(files).forEach(function (file) {
        var fileItem = document.createElement('div');
        fileItem.className = 'modern-file-item';

        var fileName = document.createElement('div');
        fileName.className = 'modern-file-name';
        fileName.innerHTML = `${icons.file}<span class="modern-file-name-text">${file.name}</span>`;

        var fileActions = document.createElement('div');
        fileActions.className = 'modern-file-actions';

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'modern-file-action-btn delete';
        deleteBtn.innerHTML = icons.trash;
        deleteBtn.type = 'button';
        deleteBtn.setAttribute('aria-label', '削除');
        deleteBtn.setAttribute('title', '削除');
        deleteBtn.onclick = function () {
          fileItem.remove();
          if (fileListDisplay.children.length === 0) {
            fileListDisplay.style.display = 'none';
            setUploadIcon('cloudUpload');
          }
        };

        fileActions.appendChild(deleteBtn);
        fileItem.appendChild(fileName);
        fileItem.appendChild(fileActions);
        fileListDisplay.appendChild(fileItem);
      });

      setUploadIcon('check');
    }

    function handleFiles(files) {
      clearFormError();
      if (!validateFiles(files)) {
        return;
      }

      renderFileList(files);
      setFileInputFiles(fileInput, files);
    }

    function bindFileSelection() {
      uploadArea.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
      });

      uploadArea.addEventListener('dragleave', function () {
        uploadArea.classList.remove('dragover');
      });

      uploadArea.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        var files = e.dataTransfer.files;
        logger.log('Files dropped:', files);
        handleFiles(files);
      });

      uploadArea.addEventListener('click', function (e) {
        if (e.target.tagName !== 'BUTTON') {
          fileInput.click();
        }
      });

      fileInput.addEventListener('change', function (e) {
        var files = e.target.files;
        logger.log('Files selected:', files);
        handleFiles(files);
      });
    }

    return {
      bindFileSelection: bindFileSelection,
      handleFiles: handleFiles
    };
  }

  modules.fileSelection = {
    createFileSelectionController: createFileSelectionController
  };
})(window);
