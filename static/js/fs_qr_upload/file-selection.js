(function (window) {
  window.FsQrUploadModules = window.FsQrUploadModules || {};
  var modules = window.FsQrUploadModules;

  function createFileSelectionController(options) {
    var uploadArea = options.uploadArea;
    var fileInput = options.fileInput;
    var fileListDisplay = options.fileListDisplay;
    var icons = options.icons;
    var clearFormError = options.clearFormError;
    var showFormError = options.showFormError;
    var setUploadIcon = options.setUploadIcon;
    var setFileInputFiles = options.setFileInputFiles;

    function validateFiles(files) {
      var MAX_FILES = 10;
      if (files.length > MAX_FILES) {
        showFormError(`ファイル数は最大${MAX_FILES}個までです。不要なファイルを外して再度お試しください。`);
        return false;
      }

      var MAX_TOTAL_SIZE = 500 * 1024 * 1024;
      var totalSize = 0;
      Array.from(files).forEach(function (file) {
        totalSize += file.size;
      });

      if (totalSize > MAX_TOTAL_SIZE) {
        var sizeMB = (totalSize / (1024 * 1024)).toFixed(2);
        showFormError(`ファイルの合計サイズは500MBまでです。現在の合計は ${sizeMB}MB です。`);
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
        console.log('Files dropped:', files);
        handleFiles(files);
      });

      uploadArea.addEventListener('click', function (e) {
        if (e.target.tagName !== 'BUTTON') {
          fileInput.click();
        }
      });

      fileInput.addEventListener('change', function (e) {
        var files = e.target.files;
        console.log('Files selected:', files);
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
