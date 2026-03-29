(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');

  function createRemoteFileListManager(options) {
    var roomId = options.roomId;
    var roomPassword = options.roomPassword;
    var csrfToken = options.csrfToken;
    var icons = options.icons;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var otherFileList = options.otherFileList;
    var downloadHandlers = options.downloadHandlers;
    var limits = options.limits || {};
    var core = modules.core || {};

    var fetchRetryCount = 0;
    var maxRetries = 3;
    var fileListSocket = null;
    var fileListReconnectDelayMs = 1000;
    var fileListReconnectTimer = null;
    var isPageUnloading = false;
    var isFetchingFileList = false;
    var shouldRefetchFileList = false;
    var lastRenderedFileSignature = null;
    var parsedFileListRequestTimeoutMs = Number(limits.fileListRequestTimeoutMs);
    var fileListRequestTimeoutMs = Number.isFinite(parsedFileListRequestTimeoutMs) && parsedFileListRequestTimeoutMs > 0
      ? parsedFileListRequestTimeoutMs
      : 1000;

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
        files.push({ name: file.name });
      }
      return files;
    }

    function setFileCount(count) {
      var fileCountElement = document.getElementById('fileCount');
      if (fileCountElement) {
        fileCountElement.textContent = String(count);
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
        otherFileList.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-medium);">まだファイルがアップロードされていません</div>';
        return;
      }

      files.forEach(function (file) {
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

        var downloadBtn = document.createElement('button');
        downloadBtn.className = 'modern-file-action-btn';
        downloadBtn.type = 'button';
        downloadBtn.innerHTML = icons.download;
        downloadBtn.setAttribute('aria-label', 'ダウンロード');
        downloadBtn.setAttribute('title', 'ダウンロード');
        downloadBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          downloadHandlers.downloadSingleFile(file, downloadBtn);
        });

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'modern-file-action-btn delete';
        deleteBtn.type = 'button';
        deleteBtn.innerHTML = icons.trash;
        deleteBtn.setAttribute('aria-label', '削除');
        deleteBtn.setAttribute('title', '削除');

        deleteBtn.addEventListener('click', function () {
          var encodedFilename = encodeURIComponent(file.name);
          if (confirm('本当にこのファイルを削除しますか？')) {
            var xhr = new window.XMLHttpRequest();
            xhr.open('DELETE', `/delete/${roomId}/${roomPassword}/${encodedFilename}`, true);
            if (csrfToken) {
              xhr.setRequestHeader('X-CSRF-Token', csrfToken);
            }
            xhr.onload = function () {
              var payload = core.safeParseJson
                ? core.safeParseJson(xhr.responseText, logger, 'group delete response')
                : null;
              if (xhr.status >= 200 && xhr.status < 300 && payload && payload.status === 'ok') {
                alert('ファイルが削除されました。');
                fetchAndDisplayOtherFiles();
              } else {
                var message = payload && typeof payload.error === 'string' ? payload.error : '削除中にエラーが発生しました。';
                alert(message);
              }
            };
            xhr.onerror = function () {
              alert('削除中にエラーが発生しました。');
            };
            xhr.send();
          }
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
      logger.warn(`ファイル情報取得失敗 (試行 ${fetchRetryCount}/${maxRetries}):`, status, error);
      if (fetchRetryCount >= maxRetries) {
        logger.error('他のユーザーのファイル情報を取得できませんでした。');
        fetchRetryCount = 0;
      }
    }

    function fetchAndDisplayOtherFiles() {
      if (isFetchingFileList) {
        shouldRefetchFileList = true;
        return;
      }

      isFetchingFileList = true;
      var xhr = new window.XMLHttpRequest();
      xhr.open('GET', `/check/${roomId}/${roomPassword}`, true);
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

        if (core.isPlainObject && core.isPlainObject(parsed) && parsed.status === 'error' && typeof parsed.error === 'string') {
          logger.warn('ファイル取得エラー:', parsed.error);
          return;
        }

        files = normalizeFileEntries(parsed);
        if (!files) {
          handleFetchFailure('unexpected_payload', 'files payload is invalid');
          return;
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

    function connectFileListWebSocket() {
      var protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      var wsUrl = `${protocol}://${window.location.host}/ws/group/${roomId}/${roomPassword}`;
      fileListSocket = new WebSocket(wsUrl);

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
          logger.warn('WebSocketメッセージ形式が不正です。');
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
          logger.warn('ファイル更新WebSocketが認証エラーで切断されました。');
          return;
        }
        scheduleFileListReconnect();
      };
    }

    function startRealtimeUpdates() {
      fetchAndDisplayOtherFiles();
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
      startRealtimeUpdates: startRealtimeUpdates
    };
  }

  modules.remoteFiles = {
    createRemoteFileListManager: createRemoteFileListManager
  };
})(window);
