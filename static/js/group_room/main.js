(function (window) {
  window.GroupRoomModules = window.GroupRoomModules || {};
  var modules = window.GroupRoomModules;
  var core = modules.core;
  var config = core.getGroupRoomConfig();
  var logger = core.createLogger(Boolean(config.debug));
  var validation = window.SharedUploadValidation;
  var rawLimits = config.limits || {};
  var parsedFileListRequestTimeoutMs = Number(rawLimits.fileListRequestTimeoutMs);
  var limits = validation.normalizeLimits(rawLimits);
  limits.fileListRequestTimeoutMs = Number.isFinite(parsedFileListRequestTimeoutMs) && parsedFileListRequestTimeoutMs > 0
    ? parsedFileListRequestTimeoutMs
    : 1000;
  var csrfToken = core.getCsrfToken();

  function initializeGroupRoom() {
    var uploadArea = document.getElementById('upload-area');
    var fileInput = document.getElementById('fileInput');
    var fileList = document.getElementById('fileList');
    var otherFileList = document.getElementById('otherFileList');
    var uploadBtn = document.getElementById('uploadBtn');
    var downloadAllBtn = document.getElementById('downloadAllBtn');
    var uploadStatusMessage = document.getElementById('uploadStatusMessage');

    if (
      !uploadArea || !fileInput || !fileList || !otherFileList ||
      !uploadBtn || !downloadAllBtn || !uploadStatusMessage
    ) {
      logger.warn('Group room初期化に必要な要素が見つかりませんでした。');
      return;
    }

    var roomId = config.roomId;
    var roomPassword = config.roomPassword;
    var icons = config.icons || {};
    var uploadButtonLabel = `${icons.rocket || ''} アップロード`;
    var uploadIconController = core.createUploadIconController(icons);

    uploadBtn.innerHTML = uploadButtonLabel;

    var downloadHandlers = modules.downloads.createDownloadHandlers({
      roomId: roomId,
      roomPassword: roomPassword,
      downloadAllBtn: downloadAllBtn,
      core: core
    });

    var remoteFileListManager = modules.remoteFiles.createRemoteFileListManager({
      roomId: roomId,
      roomPassword: roomPassword,
      csrfToken: csrfToken,
      icons: icons,
      logger: logger,
      otherFileList: otherFileList,
      downloadHandlers: downloadHandlers,
      limits: limits
    });

    var uploadQueue = modules.uploadQueue.createUploadQueue({
      uploadArea: uploadArea,
      fileInput: fileInput,
      fileList: fileList,
      icons: icons,
      setUploadIcon: uploadIconController.setUploadIcon,
      limits: limits
    });

    var uploadSubmitter = modules.uploadSubmit.createUploadSubmitter({
      uploadBtn: uploadBtn,
      uploadStatusMessage: uploadStatusMessage,
      uploadButtonLabel: uploadButtonLabel,
      roomId: roomId,
      roomPassword: roomPassword,
      csrfToken: csrfToken,
      core: core,
      logger: logger,
      getFiles: uploadQueue.getFiles,
      clearFiles: uploadQueue.clearFiles,
      limits: limits
    });

    remoteFileListManager.bindLifecycleEvents();
    remoteFileListManager.startRealtimeUpdates();

    uploadQueue.bindFileSelection();
    uploadSubmitter.bindUpload();
    downloadHandlers.bindDownloadAll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeGroupRoom);
  } else {
    initializeGroupRoom();
  }
})(window);
