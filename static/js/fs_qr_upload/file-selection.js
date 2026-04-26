(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function createFileSelectionController(options) {
    var uploadArea = options.uploadArea;
    var fileInput = options.fileInput;
    var fileListDisplay = options.fileListDisplay;
    var uploadLimitStatus = options.uploadLimitStatus;
    var icons = options.icons;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var clearFormError = options.clearFormError;
    var showFormError = options.showFormError;
    var setUploadIcon = options.setUploadIcon;
    var setFileInputFiles = options.setFileInputFiles;
    var validation = appNamespace.api.getShared('uploadValidation');
    if (!validation) {
      throw new Error('Shared upload validation is not initialized.');
    }
    var limits = validation.normalizeLimits(options.limits || {});
    var selectedFiles = [];

    function formatSize(bytes) {
      return `${Math.max(0, bytes / (1024 * 1024)).toFixed(2)}MB`;
    }

    function updateLimitStatus(files, hasInvalid) {
      if (!uploadLimitStatus) {
        return;
      }
      var totalSize = validation.calculateTotalSize(files);
      var remainingBytes = limits.maxTotalSizeBytes - totalSize;
      uploadLimitStatus.textContent = `現在 ${files.length} / 最大 ${limits.maxFiles} 件、残り ${formatSize(remainingBytes)}（上限 ${limits.maxTotalSizeMB}MB）`;
      uploadLimitStatus.classList.toggle('is-warning', Boolean(hasInvalid));
    }

    function annotateFiles(files) {
      var runningSize = 0;
      return files.map(function (file, index) {
        var reason = '';
        runningSize += file.size || 0;
        if (index >= limits.maxFiles) {
          reason = '最大件数を超えています';
        } else if (runningSize > limits.maxTotalSizeBytes) {
          reason = '合計サイズの上限を超えています';
        } else if (validation.findInvalidFilename([file]) !== null) {
          reason = 'ファイル名を変更してください';
        }
        return {
          file: file,
          invalidReason: reason
        };
      });
    }

    function validateFiles(files) {
      var result = validation.validateSelection(files, limits, { checkFileName: true });
      if (!result.ok) {
        if (result.reason === 'max_files') {
          showFormError(`ファイル数は最大${limits.maxFiles}個までです。不要なファイルを外して再度お試しください。`);
        } else if (result.reason === 'max_total_size') {
          showFormError(`ファイルの合計サイズは${limits.maxTotalSizeMB}MBまでです。現在の合計は${result.totalSizeMB}MBです。`);
        } else if (result.reason === 'invalid_filename') {
          showFormError('不正なファイル名が含まれています。ファイル名を変更して再度お試しください。');
        }
        return false;
      }

      return true;
    }

    function renderFileList(files) {
      fileListDisplay.innerHTML = '';
      if (files.length === 0) {
        fileListDisplay.style.display = 'none';
        setUploadIcon('cloudUpload');
        updateLimitStatus(files, false);
        return;
      }

      fileListDisplay.style.display = 'block';
      var annotatedFiles = annotateFiles(files);
      annotatedFiles.forEach(function (entry, index) {
        var file = entry.file;
        var fileItem = document.createElement('div');
        fileItem.className = 'modern-file-item';
        fileItem.classList.toggle('is-invalid', Boolean(entry.invalidReason));

        var fileName = document.createElement('div');
        fileName.className = 'modern-file-name';
        fileName.innerHTML = `${icons.file}<span><span class="modern-file-name-text"></span></span>`;
        var fileNameText = fileName.querySelector('.modern-file-name-text');
        if (fileNameText) {
          fileNameText.textContent = file.name;
        }
        if (entry.invalidReason) {
          var note = document.createElement('span');
          note.className = 'modern-file-item-note';
          note.textContent = entry.invalidReason;
          fileName.querySelector('span').appendChild(note);
        }

        var fileActions = document.createElement('div');
        fileActions.className = 'modern-file-actions';

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'modern-file-action-btn delete';
        deleteBtn.innerHTML = icons.trash;
        deleteBtn.type = 'button';
        deleteBtn.setAttribute('aria-label', '削除');
        deleteBtn.setAttribute('title', '削除');
        deleteBtn.onclick = function () {
          selectedFiles.splice(index, 1);
          renderFileList(selectedFiles);
          setFileInputFiles(fileInput, selectedFiles);
          clearFormError();
        };

        fileActions.appendChild(deleteBtn);
        fileItem.appendChild(fileName);
        fileItem.appendChild(fileActions);
        fileListDisplay.appendChild(fileItem);
      });

      updateLimitStatus(files, annotatedFiles.some(function (entry) { return Boolean(entry.invalidReason); }));
      setUploadIcon('check');
    }

    function handleFiles(files) {
      clearFormError();
      selectedFiles = validation.toArray(files);
      validateFiles(selectedFiles);
      renderFileList(selectedFiles);
      setFileInputFiles(fileInput, selectedFiles);
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
