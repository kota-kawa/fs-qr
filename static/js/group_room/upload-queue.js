(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');
  var core = modules.core || {};

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
    var uploadLimitStatus = document.getElementById('uploadLimitStatus');

    var filesArray = [];

    function notify(message) {
      if (typeof window.showAlertModal === 'function') {
        window.showAlertModal(message);
        return;
      }
      window.alert(message);
    }

    function formatSize(bytes) {
      return `${Math.max(0, bytes / (1024 * 1024)).toFixed(2)}MB`;
    }

    function updateLimitStatus(hasInvalid) {
      if (!uploadLimitStatus) {
        return;
      }
      var totalSize = validation.calculateTotalSize(filesArray);
      var remainingBytes = limits.maxTotalSizeBytes - totalSize;
      uploadLimitStatus.textContent = core.formatMessage
        ? core.formatMessage('upload.limit_status', 'Current {current} / max {max} files, {remaining} remaining (limit {max_size} MB)', {
          current: filesArray.length,
          max: limits.maxFiles,
          remaining: formatSize(remainingBytes),
          max_size: limits.maxTotalSizeMB
        })
        : `Current ${filesArray.length} / max ${limits.maxFiles} files, ${formatSize(remainingBytes)} remaining (limit ${limits.maxTotalSizeMB} MB)`;
      uploadLimitStatus.classList.toggle('is-warning', Boolean(hasInvalid));
    }

    function getInvalidReason(file, index, runningSize) {
      if (index >= limits.maxFiles) {
        return core.translate ? core.translate('upload.invalid_max_files_reason', 'Maximum file count exceeded') : 'Maximum file count exceeded';
      }
      if (runningSize > limits.maxTotalSizeBytes) {
        return core.translate ? core.translate('upload.invalid_total_size_reason', 'Total size limit exceeded') : 'Total size limit exceeded';
      }
      if (validation.findInvalidFilename([file]) !== null) {
        return core.translate ? core.translate('upload.invalid_filename_reason', 'Rename the file') : 'Rename the file';
      }
      return '';
    }

    function renderFileList() {
      fileList.innerHTML = '';
      if (filesArray.length === 0) {
        fileList.style.display = 'none';
        setUploadIcon('cloud');
        updateLimitStatus(false);
        return;
      }

      fileList.style.display = 'block';
      var runningSize = 0;
      var hasInvalid = false;
      filesArray.forEach(function (file, index) {
        runningSize += file.size || 0;
        var invalidReason = getInvalidReason(file, index, runningSize);
        hasInvalid = hasInvalid || Boolean(invalidReason);
        var fileItem = document.createElement('div');
        fileItem.className = 'modern-file-item';
        fileItem.classList.toggle('is-invalid', Boolean(invalidReason));

        var fileName = document.createElement('div');
        fileName.className = 'modern-file-name';
        fileName.innerHTML = `${icons.file}<span><span class="modern-file-name-text"></span></span>`;
        var fileNameText = fileName.querySelector('.modern-file-name-text');
        if (fileNameText) {
          fileNameText.textContent = file.name;
        }
        if (invalidReason) {
          var note = document.createElement('span');
          note.className = 'modern-file-item-note';
          note.textContent = invalidReason;
          fileName.querySelector('span').appendChild(note);
        }

        var actions = document.createElement('div');
        actions.className = 'modern-file-actions';

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'modern-file-action-btn delete';
        deleteBtn.type = 'button';
        deleteBtn.innerHTML = icons.trash;
        deleteBtn.setAttribute('aria-label', core.translate ? core.translate('common.delete', 'Delete') : 'Delete');
        deleteBtn.setAttribute('title', core.translate ? core.translate('common.delete', 'Delete') : 'Delete');
        deleteBtn.addEventListener('click', function () {
          filesArray.splice(index, 1);
          renderFileList();
        });

        actions.appendChild(deleteBtn);
        fileItem.appendChild(fileName);
        fileItem.appendChild(actions);
        fileList.appendChild(fileItem);
      });

      updateLimitStatus(hasInvalid);
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
          notify(core.formatMessage
            ? core.formatMessage('upload.error_max_files_with_current', 'You can upload a maximum of {max} files. You currently have {current}, and are trying to add {selected}.', {
              max: limits.maxFiles,
              current: filesArray.length,
              selected: result.selectedFilesCount
            })
            : `You can upload a maximum of ${limits.maxFiles} files. You currently have ${filesArray.length}, and are trying to add ${result.selectedFilesCount}.`);
        } else if (result.reason === 'max_total_size') {
          notify(core.formatMessage
            ? core.formatMessage('upload.error_max_size', 'The total file size limit is {max} MB. The current total is {current} MB.', { max: limits.maxTotalSizeMB, current: result.totalSizeMB })
            : `The total file size limit is ${limits.maxTotalSizeMB} MB. The current total is ${result.totalSizeMB} MB.`);
        } else if (result.reason === 'invalid_filename') {
          notify(core.translate ? core.translate('upload.invalid_filename', 'An invalid file name is included. Rename the file and try again.') : 'An invalid file name is included. Rename the file and try again.');
        }
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
