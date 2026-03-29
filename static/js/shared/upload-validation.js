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

  var sharedUploadValidation = Object.freeze({
    normalizeLimits: normalizeLimits,
    toArray: toArray,
    calculateTotalSize: calculateTotalSize,
    findInvalidFilename: findInvalidFilename,
    validateSelection: validateSelection
  });

  appNamespace.api.setShared('uploadValidation', sharedUploadValidation);
})(window);
