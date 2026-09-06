/**
 * FSQR upload file-selection adapter.
 * ドラッグ＆ドロップと一覧描画の本体は shared/file-tray.js に集約する。
 */
(function (window) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');

  function createFileSelectionController(options) {
    var shared = appNamespace.api.getShared('fileTray');
    if (!shared) {
      throw new Error('Shared file tray is not initialized.');
    }

    var tray = shared.createFileTray({
      uploadArea: options.uploadArea,
      fileInput: options.fileInput,
      fileList: options.fileListDisplay,
      uploadLimitStatus: options.uploadLimitStatus,
      icons: options.icons,
      emptyIcon: 'cloudUpload',
      setUploadIcon: options.setUploadIcon,
      logger: options.logger,
      mode: 'replace',
      failureScope: 'fsqr-selection',
      onInvalid: options.showFormError,
      onBeforeSelect: options.clearFormError,
      onRemove: options.clearFormError,
      syncInput: options.setFileInputFiles,
      limits: options.limits
    });

    return {
      bindFileSelection: tray.bindFileSelection,
      handleFiles: tray.handleFiles
    };
  }

  modules.fileSelection = {
    createFileSelectionController: createFileSelectionController
  };
})(window);
