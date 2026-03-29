(function (window) {
  window.FsQrUploadModules = window.FsQrUploadModules || {};
  var modules = window.FsQrUploadModules;

  function createRetentionPreviewController(options) {
    var retentionSelect = options.retentionSelect;
    var retentionPreviewTime = options.retentionPreviewTime;

    function formatDateTime(date) {
      function pad(value) {
        return String(value).padStart(2, '0');
      }
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    function updateRetentionPreview() {
      if (!retentionSelect || !retentionPreviewTime) {
        return;
      }
      var retentionDays = Number(retentionSelect.value || 7);
      var deletionDate = new Date();
      deletionDate.setDate(deletionDate.getDate() + retentionDays);
      retentionPreviewTime.textContent = `${formatDateTime(deletionDate)} ごろに自動削除されます`;
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
