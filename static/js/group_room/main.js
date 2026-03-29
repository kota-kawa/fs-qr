(function (window) {
  window.GroupRoomModules = window.GroupRoomModules || {};
  var modules = window.GroupRoomModules;
  var core = modules.core;
  var config = core.getGroupRoomConfig();
  var csrfToken = core.getCsrfToken();

  core.setupAjaxCsrf(csrfToken);

  $(document).ready(function () {
    var uploadArea = $('#upload-area');
    var fileInput = $('#fileInput');
    var fileList = $('#fileList');
    var otherFileList = $('#otherFileList');
    var uploadBtn = $('#uploadBtn');
    var downloadAllBtn = $('#downloadAllBtn');
    var uploadStatusMessage = $('#uploadStatusMessage');

    var roomId = config.roomId;
    var roomPassword = config.roomPassword;
    var icons = config.icons;
    var uploadButtonLabel = `${icons.rocket} アップロード`;
    var uploadIconController = core.createUploadIconController(icons);

    uploadBtn.html(uploadButtonLabel);

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
      otherFileList: otherFileList,
      downloadHandlers: downloadHandlers
    });

    var uploadQueue = modules.uploadQueue.createUploadQueue({
      uploadArea: uploadArea,
      fileInput: fileInput,
      fileList: fileList,
      icons: icons,
      setUploadIcon: uploadIconController.setUploadIcon
    });

    var uploadSubmitter = modules.uploadSubmit.createUploadSubmitter({
      uploadBtn: uploadBtn,
      uploadStatusMessage: uploadStatusMessage,
      uploadButtonLabel: uploadButtonLabel,
      roomId: roomId,
      roomPassword: roomPassword,
      csrfToken: csrfToken,
      getFiles: uploadQueue.getFiles,
      clearFiles: uploadQueue.clearFiles
    });

    remoteFileListManager.bindLifecycleEvents();
    remoteFileListManager.startRealtimeUpdates();

    uploadQueue.bindFileSelection();
    uploadSubmitter.bindUpload();
    downloadHandlers.bindDownloadAll();
  });
})(window);
