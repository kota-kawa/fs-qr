(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }

  var DANGEROUS_FILENAME_PATTERNS = ['..', '/', '\\', '\0'];

  function normalizeLimits(limits) {
    var rawLimits = limits || {};
    var parsedMaxFiles = Number(rawLimits.maxFiles);
    var parsedMaxTotalSizeBytes = Number(rawLimits.maxTotalSizeBytes);
    var parsedMaxTotalSizeMB = Number(rawLimits.maxTotalSizeMB);
    var safeMaxTotalSizeBytes = Number.isFinite(parsedMaxTotalSizeBytes) && parsedMaxTotalSizeBytes > 0
      ? parsedMaxTotalSizeBytes
      : 1;

    return {
      maxFiles: Number.isFinite(parsedMaxFiles) && parsedMaxFiles > 0 ? parsedMaxFiles : 1,
      maxTotalSizeBytes: safeMaxTotalSizeBytes,
      maxTotalSizeMB: Number.isFinite(parsedMaxTotalSizeMB) && parsedMaxTotalSizeMB > 0
        ? parsedMaxTotalSizeMB
        : Math.max(1, Math.ceil(safeMaxTotalSizeBytes / (1024 * 1024)))
    };
  }

  function toArray(files) {
    if (!files) {
      return [];
    }
    return Array.from(files);
  }

  function calculateTotalSize(files) {
    return toArray(files).reduce(function (acc, file) {
      var size = file && Number.isFinite(file.size) ? file.size : 0;
      return acc + size;
    }, 0);
  }

  function findInvalidFilename(files) {
    var fileArray = toArray(files);
    for (var i = 0; i < fileArray.length; i += 1) {
      var file = fileArray[i];
      var filename = file && typeof file.name === 'string' ? file.name : '';
      if (!filename.trim()) {
        return filename;
      }
      if (
        DANGEROUS_FILENAME_PATTERNS.some(function (pattern) {
          return filename.indexOf(pattern) !== -1;
        })
      ) {
        return filename;
      }
    }
    return null;
  }

  function validateSelection(files, limits, options) {
    var fileArray = toArray(files);
    var safeLimits = normalizeLimits(limits);
    var opts = options || {};
    var existingFilesCount = Number(opts.existingFilesCount);
    var existingTotalSize = Number(opts.existingTotalSize);
    var checkFileName = opts.checkFileName !== false;
    var safeExistingFilesCount = Number.isFinite(existingFilesCount) ? existingFilesCount : 0;
    var safeExistingTotalSize = Number.isFinite(existingTotalSize) ? existingTotalSize : 0;

    var totalFiles = safeExistingFilesCount + fileArray.length;
    if (totalFiles > safeLimits.maxFiles) {
      return {
        ok: false,
        reason: 'max_files',
        maxFiles: safeLimits.maxFiles,
        totalFiles: totalFiles,
        selectedFilesCount: fileArray.length
      };
    }

    if (checkFileName) {
      var invalidFilename = findInvalidFilename(fileArray);
      if (invalidFilename !== null) {
        return {
          ok: false,
          reason: 'invalid_filename',
          filename: invalidFilename
        };
      }
    }

    var totalSize = safeExistingTotalSize + calculateTotalSize(fileArray);
    if (totalSize > safeLimits.maxTotalSizeBytes) {
      return {
        ok: false,
        reason: 'max_total_size',
        totalSize: totalSize,
        totalSizeMB: (totalSize / (1024 * 1024)).toFixed(2),
        maxTotalSizeBytes: safeLimits.maxTotalSizeBytes,
        maxTotalSizeMB: safeLimits.maxTotalSizeMB
      };
    }

    return {
      ok: true,
      files: fileArray,
      totalFiles: totalFiles,
      totalSize: totalSize
    };
  }

  /**
   * Message catalogue for validation failures, keyed by call-site scope.
   * 検証失敗の文言表。呼び出し元ごとに従来使っていた翻訳キーと fallback をそのまま保持する。
   * `key: null` entries are landing-page strings that were never translated.
   */
  var FAILURE_MESSAGES = {
    'fsqr-selection': {
      max_files: { key: 'upload.error_max_files_remove', fallback: 'You can upload a maximum of {max} files. Remove unnecessary files and try again.' },
      max_total_size: { key: 'upload.error_max_size', fallback: 'The total file size limit is {max} MB. The current total is {current} MB.' },
      invalid_filename: { key: 'upload.invalid_filename', fallback: 'An invalid file name is included. Rename the file and try again.' }
    },
    'fsqr-submit': {
      max_files: { key: 'upload.error_max_files', fallback: 'You can upload a maximum of {max} files.' },
      max_total_size: { key: 'upload.error_max_size', fallback: 'The total file size limit is {max} MB. The current total is {current} MB.' },
      invalid_filename: { key: 'upload.invalid_filename', fallback: 'An invalid file name is included. Rename the file and try again.' }
    },
    'group-queue': {
      max_files: { key: 'upload.error_max_files_with_current', fallback: 'You can upload a maximum of {max} files. You currently have {current}, and are trying to add {selected}.' },
      max_total_size: { key: 'upload.error_max_size', fallback: 'The total file size limit is {max} MB. The current total is {current} MB.' },
      invalid_filename: { key: 'upload.invalid_filename', fallback: 'An invalid file name is included. Rename the file and try again.' }
    },
    'group-submit': {
      max_files: { key: 'upload.error_room_max_files', fallback: 'A room can hold up to {max} files in total. It currently has {current}.' },
      max_total_size: { key: 'upload.error_room_max_size', fallback: 'A room can hold up to {max} MB in total. The new total would be {current} MB.' },
      invalid_filename: { key: 'upload.invalid_filename', fallback: 'An invalid file name is included. Rename the file and try again.' }
    },
    landing: {
      max_files: { key: null, fallback: 'ファイルは合計{max}個までです。' },
      max_total_size: { key: null, fallback: 'ファイルは合計{max}MBまでです。' },
      invalid_filename: { key: null, fallback: '使用できないファイル名が含まれています。' },
      unknown: { key: null, fallback: '選択したファイルを追加できませんでした。' }
    }
  };

  /** Minimal formatter used when runtime-helpers.js is not loaded. / runtime-helpers 未読込時の簡易フォーマッタ。 */
  function fallbackFormatMessage(key, fallback, replacements) {
    var message = fallback;
    if (key && window.FSQR_I18N && typeof window.FSQR_I18N.t === 'function') {
      message = window.FSQR_I18N.t(key, fallback);
    }
    Object.keys(replacements || {}).forEach(function (name) {
      message = message.split('{' + name + '}').join(String(replacements[name]));
    });
    return message;
  }

  function resolveFormatMessage(options) {
    if (options && typeof options.formatMessage === 'function') {
      return options.formatMessage;
    }
    var helpers = appNamespace.api.getShared('runtimeHelpers');
    if (helpers && typeof helpers.formatMessage === 'function') {
      return helpers.formatMessage;
    }
    return fallbackFormatMessage;
  }

  /**
   * Turn a failed validateSelection() result into a user-facing message.
   * validateSelection() の失敗結果を利用者向け文言に変換する。
   *
   * @param {Object} result validateSelection() の戻り値（ok: false）
   * @param {Object} options { scope, existingFilesCount, formatMessage }
   * @returns {string} 表示する文言。該当文言が無い場合は空文字。
   */
  function describeFailure(result, options) {
    var opts = options || {};
    var scopeMessages = FAILURE_MESSAGES[opts.scope] || FAILURE_MESSAGES.landing;
    var reason = result && result.reason ? result.reason : 'unknown';
    var entry = scopeMessages[reason] || scopeMessages.unknown;
    if (!entry) {
      return '';
    }
    var formatMessage = resolveFormatMessage(opts);
    var existingFilesCount = Number(opts.existingFilesCount);
    var replacements = {
      max: reason === 'max_files' ? result.maxFiles : result.maxTotalSizeMB,
      current: reason === 'max_files'
        ? (Number.isFinite(existingFilesCount) ? existingFilesCount : 0)
        : result.totalSizeMB,
      selected: result.selectedFilesCount
    };
    if (!entry.key) {
      // Untranslated landing strings: fill placeholders only. / 未翻訳文言はプレースホルダー置換のみ。
      return fallbackFormatMessage(null, entry.fallback, replacements);
    }
    return formatMessage(entry.key, entry.fallback, replacements);
  }

  var sharedUploadValidation = Object.freeze({
    normalizeLimits: normalizeLimits,
    toArray: toArray,
    calculateTotalSize: calculateTotalSize,
    findInvalidFilename: findInvalidFilename,
    validateSelection: validateSelection,
    describeFailure: describeFailure
  });

  appNamespace.api.setShared('uploadValidation', sharedUploadValidation);
})(window);
