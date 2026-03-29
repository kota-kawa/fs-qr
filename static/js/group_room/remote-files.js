(function (window) {
  window.GroupRoomModules = window.GroupRoomModules || {};
  var modules = window.GroupRoomModules;

  function createRemoteFileListManager(options) {
    var roomId = options.roomId;
    var roomPassword = options.roomPassword;
    var csrfToken = options.csrfToken;
    var icons = options.icons;
    var logger = options.logger || { log: function () {}, warn: function () {}, error: function () {} };
    var otherFileList = options.otherFileList;
    var downloadHandlers = options.downloadHandlers;

    var fetchRetryCount = 0;
    var maxRetries = 3;
    var fileListSocket = null;
    var fileListReconnectDelayMs = 1000;
    var fileListReconnectTimer = null;
    var isPageUnloading = false;
    var isFetchingFileList = false;
    var shouldRefetchFileList = false;
    var lastRenderedFileSignature = null;

    function buildFileSignature(files) {
      return JSON.stringify(
        files
          .map(function (file) { return file.name; })
          .sort()
      );
    }

    function renderOtherFileList(files) {
      otherFileList.empty();
      $('#fileCount').text(files.length);

      if (files.length === 0) {
        otherFileList.html('<div style="text-align: center; padding: 2rem; color: var(--text-medium);">まだファイルがアップロードされていません</div>');
        return;
      }

      files.forEach(function (file) {
        var fileItem = $('<div class="modern-file-item"></div>');
        var fileName = $('<div class="modern-file-name"></div>');
        var fileNameText = $('<span class="modern-file-name-text"></span>').text(file.name);
        fileName.html(icons.file).append(fileNameText);

        var actions = $('<div class="modern-file-actions"></div>');

        var downloadBtn = $('<button class="modern-file-action-btn"></button>')
          .html(icons.download)
          .attr('aria-label', 'ダウンロード')
          .attr('title', 'ダウンロード');

        downloadBtn.on('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          downloadHandlers.downloadSingleFile(file, downloadBtn);
        });

        var deleteBtn = $('<button class="modern-file-action-btn delete"></button>')
          .html(icons.trash)
          .attr('aria-label', '削除')
          .attr('title', '削除');

        deleteBtn.on('click', function () {
          var encodedFilename = encodeURIComponent(file.name);
          if (confirm('本当にこのファイルを削除しますか？')) {
            $.ajax({
              url: `/delete/${roomId}/${roomPassword}/${encodedFilename}`,
              type: 'DELETE',
              headers: { 'X-CSRF-Token': csrfToken },
              success: function () {
                alert('ファイルが削除されました。');
                fetchAndDisplayOtherFiles();
              },
              error: function () {
                alert('削除中にエラーが発生しました。');
              }
            });
          }
        });

        actions.append(downloadBtn).append(deleteBtn);
        fileItem.append(fileName).append(actions);
        otherFileList.append(fileItem);
      });
    }

    function fetchAndDisplayOtherFiles() {
      if (isFetchingFileList) {
        shouldRefetchFileList = true;
        return;
      }

      isFetchingFileList = true;
      $.ajax({
        url: `/check/${roomId}/${roomPassword}`,
        type: 'GET',
        timeout: 10000,
        success: function (files) {
          fetchRetryCount = 0;

          if (files.error) {
            logger.warn('ファイル取得エラー:', files.error);
            return;
          }

          var currentFileSignature = buildFileSignature(files);
          if (currentFileSignature === lastRenderedFileSignature) {
            $('#fileCount').text(files.length);
            return;
          }

          lastRenderedFileSignature = currentFileSignature;
          renderOtherFileList(files);
        },
        error: function (xhr, status, error) {
          fetchRetryCount += 1;
          logger.warn(`ファイル情報取得失敗 (試行 ${fetchRetryCount}/${maxRetries}):`, status, error);
          if (fetchRetryCount >= maxRetries) {
            logger.error('他のユーザーのファイル情報を取得できませんでした。');
            fetchRetryCount = 0;
          }
        },
        complete: function () {
          isFetchingFileList = false;
          if (shouldRefetchFileList) {
            shouldRefetchFileList = false;
            fetchAndDisplayOtherFiles();
          }
        }
      });
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
        try {
          var payload = JSON.parse(event.data);
          if (payload.type === 'files_updated') {
            fetchAndDisplayOtherFiles();
          }
        } catch (error) {
          logger.warn('WebSocketメッセージの解析に失敗しました:', error);
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
