(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');
  var core = modules.core || {};

  function createRemoteFileListManager(options) {
    var roomId = options.roomId;
    var websocketCsrfToken = options.websocketCsrfToken;
    var csrfToken = options.csrfToken;
    var icons = options.icons;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var otherFileList = options.otherFileList;
    var downloadHandlers = options.downloadHandlers;
    var previewManager = options.previewManager;
    var limits = options.limits || {};
    var fetchRetryCount = 0;
    var maxRetries = 3;
    var fileListErrorNotified = false;
    var fileListSocket = null;
    var fileListReconnectDelayMs = 1000;
    var fileListReconnectTimer = null;
    var fileListPollTimer = null;
    var isPageUnloading = false;
    var isFetchingFileList = false;
    var shouldRefetchFileList = false;
    var lastRenderedFileSignature = null;
    var currentUsage = {
      fileCount: 0,
      totalSizeBytes: 0,
      maxFiles: Number(limits.maxFiles) || 0,
      maxTotalSizeBytes: Number(limits.maxTotalSizeBytes) || 0,
      maxTotalSizeMB: Number(limits.maxTotalSizeMB) || 0
    };
    var parsedFileListRequestTimeoutMs = Number(limits.fileListRequestTimeoutMs);
    var parsedFileListPollIntervalMs = Number(limits.fileListPollIntervalMs);
    var fileListRequestTimeoutMs = Number.isFinite(parsedFileListRequestTimeoutMs) && parsedFileListRequestTimeoutMs > 0
      ? parsedFileListRequestTimeoutMs
      : 1000;
    var fileListPollIntervalMs = Number.isFinite(parsedFileListPollIntervalMs) && parsedFileListPollIntervalMs >= 1000
      ? parsedFileListPollIntervalMs
      : 15000;

    function isValidFileEntry(file) {
      return Boolean(file) && typeof file === 'object' && typeof file.name === 'string' && file.name.length > 0;
    }

    function normalizeFileEntries(payload) {
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        return null;
      }
      if (payload.status !== 'ok') {
        return null;
      }
      if (!payload.data || typeof payload.data !== 'object' || Array.isArray(payload.data)) {
        return null;
      }
      if (!Array.isArray(payload.data.files)) {
        return null;
      }

      var files = [];
      for (var i = 0; i < payload.data.files.length; i += 1) {
        var file = payload.data.files[i];
        if (!isValidFileEntry(file)) {
          return null;
        }
        files.push({
          name: file.name,
          previewable: file.previewable === true,
          previewType: typeof file.preview_type === 'string' ? file.preview_type : '',
          previewMimeType: typeof file.preview_mime_type === 'string' ? file.preview_mime_type : ''
        });
      }
      return files;
    }

    function setFileCount(count) {
      var fileCountElement = document.getElementById('fileCount');
      if (fileCountElement) {
        fileCountElement.textContent = String(count);
      }
    }

    function formatSize(bytes) {
      var safeBytes = Number.isFinite(bytes) && bytes > 0 ? bytes : 0;
      if (safeBytes >= 1024 * 1024 * 1024) {
        return (safeBytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
      }
      if (safeBytes >= 1024 * 1024) {
        return (safeBytes / (1024 * 1024)).toFixed(1) + ' MB';
      }
      if (safeBytes >= 1024) {
        return (safeBytes / 1024).toFixed(1) + ' KB';
      }
      return String(Math.round(safeBytes)) + ' B';
    }

    function normalizeUsage(payload) {
      if (!payload || typeof payload !== 'object' || !payload.data || typeof payload.data !== 'object') {
        return null;
      }
      var usage = payload.data.usage;
      if (!usage || typeof usage !== 'object') {
        return null;
      }
      return {
        fileCount: Number(usage.file_count) || 0,
        totalSizeBytes: Number(usage.total_size_bytes) || 0,
        maxFiles: Number(usage.max_files) || currentUsage.maxFiles,
        maxTotalSizeBytes: Number(usage.max_total_size_bytes) || currentUsage.maxTotalSizeBytes,
        maxTotalSizeMB: Number(usage.max_total_size_mb) || currentUsage.maxTotalSizeMB
      };
    }

    function renderUsage(usage) {
      currentUsage = usage;
      var usageContainer = document.getElementById('roomUsage');
      var usageText = document.getElementById('roomUsageText');
      var usageBarFill = document.getElementById('roomUsageBarFill');
      var maxBytes = usage.maxTotalSizeBytes > 0
        ? usage.maxTotalSizeBytes
        : usage.maxTotalSizeMB * 1024 * 1024;

      if (usageText) {
        usageText.textContent = core.formatMessage
          ? core.formatMessage('group.usage_summary', 'Usage {used} / {total} · {count} / {maxCount} files', {
            used: formatSize(usage.totalSizeBytes),
            total: formatSize(maxBytes),
            count: usage.fileCount,
            maxCount: usage.maxFiles
          })
          : `Usage ${formatSize(usage.totalSizeBytes)} / ${formatSize(maxBytes)} · ${usage.fileCount} / ${usage.maxFiles} files`;
      }

      var isFull = (maxBytes > 0 && usage.totalSizeBytes >= maxBytes) ||
        (usage.maxFiles > 0 && usage.fileCount >= usage.maxFiles);

      if (usageBarFill) {
        var ratio = maxBytes > 0 ? Math.min(1, usage.totalSizeBytes / maxBytes) : 0;
        usageBarFill.style.width = `${Math.round(ratio * 100)}%`;
      }

      if (usageContainer) {
        usageContainer.classList.toggle('is-full', isFull);
      }
    }

    function clearChildren(element) {
      while (element.firstChild) {
        element.removeChild(element.firstChild);
      }
    }

    function buildFileSignature(files) {
      return JSON.stringify(
        files
          .map(function (file) { return file.name; })
          .sort()
      );
    }

    function renderOtherFileList(files) {
      clearChildren(otherFileList);
      setFileCount(files.length);

      if (files.length === 0) {
        var emptyMessage = document.createElement('div');
        emptyMessage.style.textAlign = 'center';
        emptyMessage.style.padding = '2rem';
        emptyMessage.style.color = 'var(--text-medium)';
        emptyMessage.textContent = core.translate ? core.translate('group.no_files_yet', 'No files uploaded yet') : 'No files uploaded yet';
        otherFileList.appendChild(emptyMessage);
        return;
      }

      files.forEach(function (file) {
        var fileItem = document.createElement('div');
        fileItem.className = 'modern-file-item';

        var fileName = document.createElement('div');
        fileName.className = 'modern-file-name';
        fileName.innerHTML = `${icons.file}<span class="modern-file-name-info"><span class="modern-file-name-text"></span></span>`;
        var fileNameText = fileName.querySelector('.modern-file-name-text');
        if (fileNameText) {
          fileNameText.textContent = file.name;
        }

        var actions = document.createElement('div');
        actions.className = 'modern-file-actions';

        if (file.previewable && previewManager && typeof previewManager.previewFile === 'function') {
          var previewBtn = document.createElement('button');
          previewBtn.className = 'modern-file-action-btn';
          previewBtn.type = 'button';
          previewBtn.innerHTML = icons.preview || icons.file;
          previewBtn.setAttribute('aria-label', core.translate ? core.translate('common.preview', 'Preview') : 'Preview');
          previewBtn.setAttribute('title', core.translate ? core.translate('common.preview', 'Preview') : 'Preview');
          previewBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            previewManager.previewFile(file);
          });
          actions.appendChild(previewBtn);
        }

        var downloadBtn = document.createElement('button');
        downloadBtn.className = 'modern-file-action-btn';
        downloadBtn.type = 'button';
        downloadBtn.innerHTML = icons.download;
        downloadBtn.setAttribute('aria-label', core.translate ? core.translate('common.download', 'Download') : 'Download');
        downloadBtn.setAttribute('title', core.translate ? core.translate('common.download', 'Download') : 'Download');
        downloadBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          downloadHandlers.downloadSingleFile(file, downloadBtn);
        });

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'modern-file-action-btn delete';
        deleteBtn.type = 'button';
        deleteBtn.innerHTML = icons.trash;
        deleteBtn.setAttribute('aria-label', core.translate ? core.translate('common.delete', 'Delete') : 'Delete');
        deleteBtn.setAttribute('title', core.translate ? core.translate('common.delete', 'Delete') : 'Delete');

        deleteBtn.addEventListener('click', async function () {
          var encodedFilename = encodeURIComponent(file.name);
          var confirmed = await window.showConfirmModal(
            core.formatMessage ? core.formatMessage('group.delete_confirm', 'This will delete "{name}". This cannot be undone.', { name: file.name }) : `This will delete "${file.name}". This cannot be undone.`,
            {
              title: core.translate ? core.translate('group.delete_file_title', 'Delete file') : 'Delete file',
              confirmLabel: core.translate ? core.translate('alert.delete', 'Delete') : 'Delete'
            }
          );
          if (!confirmed) {
            return;
          }

          var xhr = new window.XMLHttpRequest();
          xhr.open('DELETE', `/delete/${roomId}/${encodedFilename}`, true);
          if (csrfToken) {
            xhr.setRequestHeader('X-CSRF-Token', csrfToken);
          }
          xhr.onload = function () {
            var payload = core.safeParseJson
              ? core.safeParseJson(xhr.responseText, logger, 'group delete response')
              : null;
            if (xhr.status >= 200 && xhr.status < 300 && payload && payload.status === 'ok') {
              window.showAlertModal(core.translate ? core.translate('group.file_deleted', 'File deleted.') : 'File deleted.');
              fetchAndDisplayOtherFiles();
            } else {
              var message = payload && typeof payload.error === 'string' ? payload.error : (core.translate ? core.translate('group.delete_error', 'An error occurred while deleting.') : 'An error occurred while deleting.');
              window.showAlertModal(message);
            }
          };
          xhr.onerror = function () {
            window.showAlertModal(core.translate ? core.translate('group.delete_error', 'An error occurred while deleting.') : 'An error occurred while deleting.');
          };
          xhr.send();
        });

        actions.appendChild(downloadBtn);
        actions.appendChild(deleteBtn);
        fileItem.appendChild(fileName);
        fileItem.appendChild(actions);
        otherFileList.appendChild(fileItem);
      });
    }

    function handleFetchFailure(status, error) {
      fetchRetryCount += 1;
      logger.warn(`File list fetch failed (attempt ${fetchRetryCount}/${maxRetries}):`, status, error);
      if (fetchRetryCount >= maxRetries) {
        logger.error('Could not fetch files from other users.');
        fetchRetryCount = 0;
        // Surface a subtle, non-blocking notice once per failure streak so the
        // user understands the list may be stale on a slow/flaky connection.
        if (!fileListErrorNotified && window.FSQRUx && typeof window.FSQRUx.toast === 'function') {
          fileListErrorNotified = true;
          var msg = core.translate
            ? core.translate('group.file_list_stale', 'ファイル一覧を更新できませんでした。接続を確認しています…')
            : 'ファイル一覧を更新できませんでした。接続を確認しています…';
          window.FSQRUx.toast(msg, { type: 'error' });
        }
      }
    }

    function fetchAndDisplayOtherFiles() {
      if (isFetchingFileList) {
        shouldRefetchFileList = true;
        return;
      }

      isFetchingFileList = true;
      var xhr = new window.XMLHttpRequest();
      xhr.open('GET', `/check/${roomId}`, true);
      xhr.timeout = fileListRequestTimeoutMs;
      xhr.onload = function () {
        if (!(xhr.status >= 200 && xhr.status < 300)) {
          handleFetchFailure('http_error', `status=${xhr.status}`);
          return;
        }

        var files;
        var parsed = core.safeParseJson
          ? core.safeParseJson(xhr.responseText, logger, 'group file list')
          : null;
        if (parsed === null) {
          handleFetchFailure('parse_error', 'invalid json');
          return;
        }

        fetchRetryCount = 0;
        fileListErrorNotified = false;

        if (core.isPlainObject && core.isPlainObject(parsed) && parsed.status === 'error' && typeof parsed.error === 'string') {
          logger.warn('File fetch error:', parsed.error);
          return;
        }

        files = normalizeFileEntries(parsed);
        if (!files) {
          handleFetchFailure('unexpected_payload', 'files payload is invalid');
          return;
        }

        var usage = normalizeUsage(parsed);
        if (usage) {
          renderUsage(usage);
        }

        var currentFileSignature = buildFileSignature(files);
        if (currentFileSignature === lastRenderedFileSignature) {
          setFileCount(files.length);
          return;
        }

        lastRenderedFileSignature = currentFileSignature;
        renderOtherFileList(files);
      };
      xhr.onerror = function () {
        handleFetchFailure('network_error', 'network');
      };
      xhr.ontimeout = function () {
        handleFetchFailure('timeout', 'timeout');
      };
      xhr.onloadend = function () {
        isFetchingFileList = false;
        if (shouldRefetchFileList) {
          shouldRefetchFileList = false;
          fetchAndDisplayOtherFiles();
        }
      };
      xhr.send();
    }

    function scheduleFileListReconnect() {
      if (fileListReconnectTimer) {
        clearTimeout(fileListReconnectTimer);
      }

      fileListReconnectTimer = setTimeout(function () {
        connectFileListWebSocket();
      }, fileListReconnectDelayMs);
      fileListReconnectDelayMs = Math.min(fileListReconnectDelayMs * 2, 30000);
    }

    function stopPolling() {
      if (fileListPollTimer) {
        clearInterval(fileListPollTimer);
        fileListPollTimer = null;
      }
    }

    function startPolling() {
      stopPolling();
      fileListPollTimer = setInterval(function () {
        if (document.visibilityState === 'hidden') {
          return;
        }
        fetchAndDisplayOtherFiles();
      }, fileListPollIntervalMs);
    }

    function connectFileListWebSocket() {
      var protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      var wsUrl = new URL(`${protocol}://${window.location.host}/ws/group/${roomId}`);
      if (websocketCsrfToken) {
        wsUrl.searchParams.set('csrf_token', websocketCsrfToken);
      }
      fileListSocket = new WebSocket(wsUrl.toString());

      fileListSocket.onopen = function () {
        fileListReconnectDelayMs = 1000;
        if (fileListReconnectTimer) {
          clearTimeout(fileListReconnectTimer);
          fileListReconnectTimer = null;
        }
        fetchAndDisplayOtherFiles();
      };

      fileListSocket.onmessage = function (event) {
        var payload = core.safeParseJson
          ? core.safeParseJson(event && event.data, logger, 'group websocket message')
          : null;
        if (!payload) {
          return;
        }
        if (typeof payload !== 'object' || Array.isArray(payload)) {
          logger.warn('Invalid WebSocket message payload.');
          return;
        }
        if (payload.type === 'files_updated') {
          fetchAndDisplayOtherFiles();
        }
      };

      fileListSocket.onerror = function () {
        if (fileListSocket && fileListSocket.readyState === WebSocket.OPEN) {
          fileListSocket.close();
        }
      };

      fileListSocket.onclose = function (event) {
        if (isPageUnloading) {
          return;
        }
        if (event && event.code === 1008) {
          logger.warn('File update WebSocket closed with an authentication error.');
          return;
        }
        scheduleFileListReconnect();
      };
    }

    function startRealtimeUpdates() {
      renderUsage(currentUsage);
      fetchAndDisplayOtherFiles();
      startPolling();
      connectFileListWebSocket();
    }

    function bindLifecycleEvents() {
      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible') {
          fetchAndDisplayOtherFiles();
          if (
            !fileListSocket ||
            fileListSocket.readyState === WebSocket.CLOSING ||
            fileListSocket.readyState === WebSocket.CLOSED
          ) {
            connectFileListWebSocket();
          }
        }
      });

      window.addEventListener('beforeunload', function () {
        isPageUnloading = true;
        if (fileListReconnectTimer) {
          clearTimeout(fileListReconnectTimer);
        }
        stopPolling();
        if (
          fileListSocket &&
          (
            fileListSocket.readyState === WebSocket.OPEN ||
            fileListSocket.readyState === WebSocket.CONNECTING
          )
        ) {
          fileListSocket.close();
        }
      });
    }

    return {
      fetchAndDisplayOtherFiles: fetchAndDisplayOtherFiles,
      bindLifecycleEvents: bindLifecycleEvents,
      startRealtimeUpdates: startRealtimeUpdates,
      getUsage: function () {
        return {
          fileCount: currentUsage.fileCount,
          totalSizeBytes: currentUsage.totalSizeBytes,
          maxFiles: currentUsage.maxFiles,
          maxTotalSizeBytes: currentUsage.maxTotalSizeBytes,
          maxTotalSizeMB: currentUsage.maxTotalSizeMB
        };
      }
    };
  }

  modules.remoteFiles = {
    createRemoteFileListManager: createRemoteFileListManager
  };
})(window);
