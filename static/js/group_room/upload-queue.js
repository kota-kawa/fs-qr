/**
 * Group upload queue adapter.
 * Group は既存ファイルへ追加するため append モードだけを指定し、共通 tray を使う。
 */
(function (window) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('groupRoom');

  function createUploadQueue(options) {
    var shared = appNamespace.api.getShared('fileTray');
    if (!shared) {
      throw new Error('Shared file tray is not initialized.');
    }

    var tray = shared.createFileTray({
      uploadArea: options.uploadArea,
      fileInput: options.fileInput,
      fileList: options.fileList,
      uploadLimitStatus: document.getElementById('uploadLimitStatus'),
      icons: options.icons,
      emptyIcon: 'cloud',
      setUploadIcon: options.setUploadIcon,
      logger: options.logger,
      mode: 'append',
      failureScope: 'group-queue',
      onInvalid: function (message) {
        if (typeof window.showAlertModal === 'function') {
          window.showAlertModal(message);
        } else {
          window.alert(message);
        }
      },
      filePickerButton: document.getElementById('uploadFileBtn'),
      stopDragPropagation: true,
      limits: options.limits
    });

    return {
      bindFileSelection: tray.bindFileSelection,
      getFiles: tray.getFiles,
      clearFiles: tray.clearFiles
    };
  }

  modules.uploadQueue = {
    createUploadQueue: createUploadQueue
  };
})(window);
