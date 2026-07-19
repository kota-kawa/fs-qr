(function (window) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var modules = appNamespace.api.getModuleNamespace('fsQrUpload');
  var core = modules.core || {};

  function createRetentionPreviewController(options) {
    var retentionSelect = options.retentionSelect;
    var retentionPreviewTime = options.retentionPreviewTime;
    var retentionAutoDeleteTemplate = options.retentionAutoDeleteTemplate
      || (core.translate ? core.translate('retention.auto_delete_at', 'Will be automatically deleted around {time}') : 'Will be automatically deleted around {time}');

    function formatDateTime(date) {
      function pad(value) {
        return String(value).padStart(2, '0');
      }
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    function formatRetentionAutoDeleteText(timeText) {
      return retentionAutoDeleteTemplate.replace('{time}', timeText);
    }

    function updateRetentionPreview() {
      if (!retentionSelect || !retentionPreviewTime) {
        return;
      }
      var retentionHours = Number(retentionSelect.value || 24);
      var deletionDate = new Date();
      deletionDate.setHours(deletionDate.getHours() + retentionHours);
      retentionPreviewTime.textContent = formatRetentionAutoDeleteText(formatDateTime(deletionDate));
    }

    function bindRetentionEvents() {
      if (retentionSelect) {
        retentionSelect.addEventListener('change', updateRetentionPreview);
      }
    }

    return {
      updateRetentionPreview: updateRetentionPreview,
      bindRetentionEvents: bindRetentionEvents
    };
  }

  modules.retention = {
    createRetentionPreviewController: createRetentionPreviewController
  };
})(window);
