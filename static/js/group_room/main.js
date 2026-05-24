(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');
  var core = modules.core;
  var config = core.getGroupRoomConfig();
  var logger = core.createLogger(Boolean(config.debug));
  var validation = appNamespace.api.getShared('uploadValidation');
  if (!validation) {
    throw new Error('Shared upload validation is not initialized.');
  }
  var rawLimits = config.limits || {};
  var parsedFileListRequestTimeoutMs = Number(rawLimits.fileListRequestTimeoutMs);
  var parsedFileListPollIntervalMs = Number(rawLimits.fileListPollIntervalMs);
  var limits = validation.normalizeLimits(rawLimits);
  limits.fileListRequestTimeoutMs = Number.isFinite(parsedFileListRequestTimeoutMs) && parsedFileListRequestTimeoutMs > 0
    ? parsedFileListRequestTimeoutMs
    : 1000;
  limits.fileListPollIntervalMs = Number.isFinite(parsedFileListPollIntervalMs) && parsedFileListPollIntervalMs >= 1000
    ? parsedFileListPollIntervalMs
    : 15000;
  var csrfToken = core.getCsrfToken();

  function initializeGroupRoom() {
    var uploadArea = document.getElementById('upload-area');
    var fileInput = document.getElementById('fileInput');
    var fileList = document.getElementById('fileList');
    var otherFileList = document.getElementById('otherFileList');
    var uploadBtn = document.getElementById('uploadBtn');
    var downloadAllBtn = document.getElementById('downloadAllBtn');
    var uploadStatusMessage = document.getElementById('uploadStatusMessage');
    var previewOverlay = document.getElementById('groupPreviewOverlay');
    var previewDialog = previewOverlay ? previewOverlay.querySelector('.group-preview-dialog') : null;
    var previewTitle = document.getElementById('groupPreviewTitle');
    var previewBody = document.getElementById('groupPreviewBody');
    var previewCloseButton = document.getElementById('groupPreviewClose');
    var previewDownloadLink = document.getElementById('groupPreviewDownloadLink');

    if (
      !uploadArea || !fileInput || !fileList || !otherFileList ||
      !uploadBtn || !downloadAllBtn || !uploadStatusMessage ||
      !previewOverlay || !previewDialog || !previewTitle || !previewBody ||
      !previewCloseButton || !previewDownloadLink
    ) {
      logger.warn('Required elements for group room initialization were not found.');
      return;
    }

    var roomId = config.roomId;
    var websocketCsrfToken = config.websocketCsrfToken;
    var icons = config.icons || {};
    var uploadButtonLabel = `${icons.rocket || ''} ${core.translate('upload.upload', 'Upload')}`;
    var uploadIconController = core.createUploadIconController(icons);

    uploadBtn.innerHTML = uploadButtonLabel;

    var downloadHandlers = modules.downloads.createDownloadHandlers({
      roomId: roomId,
      downloadAllBtn: downloadAllBtn,
      core: core
    });

    var previewManager = modules.preview.createPreviewManager({
      roomId: roomId,
      overlay: previewOverlay,
      dialog: previewDialog,
      title: previewTitle,
      body: previewBody,
      closeButton: previewCloseButton,
      downloadLink: previewDownloadLink,
      logger: logger
    });

    var remoteFileListManager = modules.remoteFiles.createRemoteFileListManager({
      roomId: roomId,
      websocketCsrfToken: websocketCsrfToken,
      csrfToken: csrfToken,
      icons: icons,
      logger: logger,
      otherFileList: otherFileList,
      downloadHandlers: downloadHandlers,
      previewManager: previewManager,
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
      csrfToken: csrfToken,
      core: core,
      logger: logger,
      getFiles: uploadQueue.getFiles,
      clearFiles: uploadQueue.clearFiles,
      refreshRemoteFiles: remoteFileListManager.fetchAndDisplayOtherFiles,
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
