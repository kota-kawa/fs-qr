/**
 * Shared upload file tray (drop zone + selected file list).
 * FSQR の file-selection.js と Group の upload-queue.js で同一だった
 * ドラッグ＆ドロップ、ファイル一覧の描画、上限表示をまとめたモジュール。
 *
 * createFileTray({
 *   uploadArea, fileInput, fileList, uploadLimitStatus,
 *   icons: { file, trash }, emptyIcon: 'cloudUpload' | 'cloud', setUploadIcon,
 *   limits, logger,
 *   mode: 'replace' | 'append',        // FSQR replaces the selection, Group appends to it
 *   failureScope: 'fsqr-selection' | 'group-queue',
 *   onInvalid(message),                // FSQR: inline form error, Group: alert modal
 *   onBeforeSelect(), onRemove(files), // FSQR clears the inline form error
 *   syncInput(fileInput, files),       // FSQR keeps <input type=file> in sync
 *   filePickerButton,                  // Group-only #uploadFileBtn
 *   stopDragPropagation                // Group also stops propagation of drag events
 * })
 */
(function (window, document) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var helpers = appNamespace.api.getShared('runtimeHelpers');
  if (!helpers) {
    throw new Error('Shared runtime helpers are not initialized.');
  }
  var validation = appNamespace.api.getShared('uploadValidation');
  if (!validation) {
    throw new Error('Shared upload validation is not initialized.');
  }

  var NOOP_LOGGER = { log: function () {}, warn: function () {}, error: function () {} };

  function createFileTray(options) {
    var uploadArea = options.uploadArea;
    var fileInput = options.fileInput;
    var fileList = options.fileList;
    var uploadLimitStatus = options.uploadLimitStatus || null;
    var icons = options.icons || {};
    var emptyIcon = options.emptyIcon || 'cloudUpload';
    var setUploadIcon = typeof options.setUploadIcon === 'function' ? options.setUploadIcon : function () {};
    var logger = options.logger || NOOP_LOGGER;
    var mode = options.mode === 'append' ? 'append' : 'replace';
    var failureScope = options.failureScope || 'fsqr-selection';
    var onInvalid = typeof options.onInvalid === 'function' ? options.onInvalid : function () {};
    var onBeforeSelect = typeof options.onBeforeSelect === 'function' ? options.onBeforeSelect : function () {};
    var onRemove = typeof options.onRemove === 'function' ? options.onRemove : function () {};
    var syncInput = typeof options.syncInput === 'function' ? options.syncInput : null;
    var filePickerButton = options.filePickerButton || null;
    var stopDragPropagation = Boolean(options.stopDragPropagation);
    var limits = validation.normalizeLimits(options.limits || {});

    var files = [];

    function formatSize(bytes) {
      return Math.max(0, bytes / (1024 * 1024)).toFixed(2) + 'MB';
    }

    /** "Current n / max m files, … remaining" line. / 上限に対する現在の状態を表示する。 */
    function updateLimitStatus(hasInvalid) {
      if (!uploadLimitStatus) {
        return;
      }
      var totalSize = validation.calculateTotalSize(files);
      var remainingBytes = limits.maxTotalSizeBytes - totalSize;
      uploadLimitStatus.textContent = helpers.formatMessage(
        'upload.limit_status',
        'Current {current} / max {max} files, {remaining} remaining (limit {max_size} MB)',
        {
          current: files.length,
          max: limits.maxFiles,
          remaining: formatSize(remainingBytes),
          max_size: limits.maxTotalSizeMB
        }
      );
      uploadLimitStatus.classList.toggle('is-warning', Boolean(hasInvalid));
    }

    /** Why a single entry would be rejected, for the inline note. / 一覧の注記に使う個別ファイルの不備理由。 */
    function getInvalidReason(file, index, runningSize) {
      if (index >= limits.maxFiles) {
        return helpers.translate('upload.invalid_max_files_reason', 'Maximum file count exceeded');
      }
      if (runningSize > limits.maxTotalSizeBytes) {
        return helpers.translate('upload.invalid_total_size_reason', 'Total size limit exceeded');
      }
      if (validation.findInvalidFilename([file]) !== null) {
        return helpers.translate('upload.invalid_filename_reason', 'Rename the file');
      }
      return '';
    }

    function syncInputFiles() {
      if (syncInput && fileInput) {
        syncInput(fileInput, files);
      }
    }

    function removeAt(index) {
      files.splice(index, 1);
      renderFileList();
      syncInputFiles();
      onRemove(files);
    }

    function renderFileList() {
      fileList.innerHTML = '';
      if (files.length === 0) {
        fileList.style.display = 'none';
        setUploadIcon(emptyIcon);
        updateLimitStatus(false);
        return;
      }

      fileList.style.display = 'block';
      var runningSize = 0;
      var hasInvalid = false;
      var deleteLabel = helpers.translate('common.delete', 'Delete');

      files.forEach(function (file, index) {
        runningSize += file.size || 0;
        var invalidReason = getInvalidReason(file, index, runningSize);
        hasInvalid = hasInvalid || Boolean(invalidReason);

        var fileItem = document.createElement('div');
        fileItem.className = 'modern-file-item';
        fileItem.classList.toggle('is-invalid', Boolean(invalidReason));

        // Icons come from the server-rendered config (trusted markup); the file name is set via textContent.
        // アイコンはサーバー側で生成した信頼できるマークアップ。ファイル名は textContent で反映する。
        var fileName = document.createElement('div');
        fileName.className = 'modern-file-name';
        fileName.innerHTML = (icons.file || '') + '<span class="modern-file-name-info"><span class="modern-file-name-text"></span></span>';
        var fileNameInfo = fileName.querySelector('.modern-file-name-info');
        var fileNameText = fileName.querySelector('.modern-file-name-text');
        if (fileNameText) {
          fileNameText.textContent = file.name;
        }
        if (invalidReason && fileNameInfo) {
          var note = document.createElement('span');
          note.className = 'modern-file-item-note';
          note.textContent = invalidReason;
          fileNameInfo.appendChild(note);
        }

        var actions = document.createElement('div');
        actions.className = 'modern-file-actions';

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'modern-file-action-btn delete';
        deleteBtn.type = 'button';
        deleteBtn.innerHTML = icons.trash || '';
        deleteBtn.setAttribute('aria-label', deleteLabel);
        deleteBtn.setAttribute('title', deleteLabel);
        deleteBtn.addEventListener('click', function () {
          removeAt(index);
        });

        actions.appendChild(deleteBtn);
        fileItem.appendChild(fileName);
        fileItem.appendChild(actions);
        fileList.appendChild(fileItem);
      });

      updateLimitStatus(hasInvalid);
      setUploadIcon('check');
    }

    /**
     * Accept newly picked files. Validation failures are reported but the files
     * are still listed (and annotated) so the user can fix the selection.
     * 新しく選ばれたファイルを受け入れる。検証に失敗しても一覧には載せ、注記で修正を促す。
     */
    function handleFiles(incoming) {
      onBeforeSelect();
      var selectedFiles = validation.toArray(incoming);
      var result;

      if (mode === 'append') {
        result = validation.validateSelection(selectedFiles, limits, {
          existingFilesCount: files.length,
          existingTotalSize: validation.calculateTotalSize(files),
          checkFileName: true
        });
        if (!result.ok) {
          var appendMessage = validation.describeFailure(result, {
            scope: failureScope,
            existingFilesCount: files.length
          });
          if (appendMessage) {
            onInvalid(appendMessage);
          }
        }
        files = files.concat(selectedFiles);
      } else {
        files = selectedFiles;
        result = validation.validateSelection(files, limits, { checkFileName: true });
        if (!result.ok) {
          var replaceMessage = validation.describeFailure(result, { scope: failureScope });
          if (replaceMessage) {
            onInvalid(replaceMessage);
          }
        }
      }

      renderFileList();
      syncInputFiles();
    }

    function stopEvent(event) {
      event.preventDefault();
      if (stopDragPropagation) {
        event.stopPropagation();
      }
    }

    function bindFileSelection() {
      uploadArea.addEventListener('dragover', function (event) {
        stopEvent(event);
        uploadArea.classList.add('dragover');
      });

      uploadArea.addEventListener('dragleave', function (event) {
        if (stopDragPropagation) {
          stopEvent(event);
        }
        uploadArea.classList.remove('dragover');
      });

      uploadArea.addEventListener('drop', function (event) {
        stopEvent(event);
        uploadArea.classList.remove('dragover');
        var dropped = event.dataTransfer.files;
        logger.log('Files dropped:', dropped);
        handleFiles(dropped);
      });

      uploadArea.addEventListener('click', function (event) {
        if (event.target.tagName !== 'BUTTON') {
          fileInput.click();
        }
      });

      if (filePickerButton) {
        filePickerButton.addEventListener('click', function (event) {
          event.preventDefault();
          event.stopPropagation();
          fileInput.click();
        });
      }

      fileInput.addEventListener('change', function () {
        var picked = fileInput.files;
        logger.log('Files selected:', picked);
        handleFiles(picked);
      });
    }

    function getFiles() {
      return files;
    }

    function clearFiles() {
      files = [];
      renderFileList();
      syncInputFiles();
    }

    return {
      bindFileSelection: bindFileSelection,
      handleFiles: handleFiles,
      renderFileList: renderFileList,
      getFiles: getFiles,
      clearFiles: clearFiles
    };
  }

  appNamespace.api.setShared('fileTray', Object.freeze({
    createFileTray: createFileTray
  }));
})(window, document);
