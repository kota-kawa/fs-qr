(function (window) {
  window.FsQrUploadModules = window.FsQrUploadModules || {};
  var modules = window.FsQrUploadModules;
  var core = modules.core;
  var config = core.getFsQrUploadConfig();
  var logger = core.createLogger(Boolean(config.debug));
  var limits = window.SharedUploadValidation.normalizeLimits(config.limits || {});
  var elements = core.getElements();

  var formError = core.createFormErrorController(elements.inlineError);
  var uploadIconController = core.createUploadIconController(config.icons || {});
  var spinnerController = modules.spinner.createSpinnerController({
    spinnerRoot: elements.spinnerRoot,
    spinnerText: elements.spinnerText,
    spinnerProgress: elements.spinnerProgress
  });

  var retentionController = modules.retention.createRetentionPreviewController({
    retentionSelect: elements.retentionSelect,
    retentionPreviewTime: elements.retentionPreviewTime
  });

  var idModeController = modules.idMode.createIdModeController({
    idInput: elements.idInput,
    clearFormError: formError.clearFormError
  });

  var fileSelectionController = modules.fileSelection.createFileSelectionController({
    uploadArea: elements.uploadArea,
    fileInput: elements.fileInput,
    fileListDisplay: elements.fileListDisplay,
    icons: config.icons || {},
    logger: logger,
    clearFormError: formError.clearFormError,
    showFormError: formError.showFormError,
    setUploadIcon: uploadIconController.setUploadIcon,
    setFileInputFiles: core.setFileInputFiles,
    limits: limits
  });

  var encryptionService = modules.encryption.createEncryptionService({
    setProgressScale: spinnerController.setProgressScale
  });

  var uploadSubmitter = modules.uploadSubmit.createUploadSubmitter({
    uploadForm: elements.uploadForm,
    fileInput: elements.fileInput,
    retentionSelect: elements.retentionSelect,
    getCurrentId: idModeController.getCurrentId,
    clearFormError: formError.clearFormError,
    showFormError: formError.showFormError,
    csrfToken: core.getCsrfToken(),
    spinner: spinnerController,
    encryptionService: encryptionService,
    limits: limits
  });

  function initializeStaticUi() {
    var uploadButtonLabel = `${config.icons.rocket} アップロード開始`;
    if (elements.startUploadBtn) {
      elements.startUploadBtn.innerHTML = uploadButtonLabel;
    }
    uploadIconController.setUploadIcon('cloudUpload');
  }

  function bindAllEvents() {
    initializeStaticUi();
    idModeController.bindIdModeToggle();
    idModeController.bindIdValidation();
    retentionController.bindRetentionEvents();
    fileSelectionController.bindFileSelection();
    uploadSubmitter.bindUpload();
  }

  bindAllEvents();
  document.addEventListener('DOMContentLoaded', function () {
    idModeController.setupInitialAutoId();
    retentionController.updateRetentionPreview();
  });
})(window);
