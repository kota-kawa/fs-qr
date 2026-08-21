(function (window) {
  'use strict';

  var app = window.__FSQR_APP__;
  if (!app || !app.api) return;

  var modules = app.api.getModuleNamespace('taskBoard');

  var exportBtn = document.getElementById('taskExportBtn');
  var importBtn = document.getElementById('taskImportBtn');
  var importInput = document.getElementById('taskImportInput');

  // インポートボタンは input[type=file] を包む <label> のため、マウスクリックは
  // ネイティブに委譲されるがキーボードでは反応しない。Enter / Space で
  // ファイル選択を開けるよう補う。
  // The import button is a <label> wrapping the file input: mouse clicks are
  // forwarded natively, but a label has no keyboard activation, so Enter and
  // Space are wired up here to open the file picker.
  if (importBtn && importInput) {
    importBtn.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Spacebar') return;
      event.preventDefault();
      importInput.click();
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener('click', function () {
      var roomId = modules.core.config.roomId;
      var url = '/api/task/' + encodeURIComponent(roomId) + '/export';

      fetch(url, { method: 'GET' })
        .then(function (response) {
          if (!response.ok) {
            throw new Error('Export failed');
          }
          var disposition = response.headers.get('Content-Disposition');
          var filename = 'tasks.json';
          if (disposition && disposition.indexOf('filename=') !== -1) {
            var matches = disposition.match(/filename="?([^"]+)"?/);
            if (matches && matches[1]) {
              filename = matches[1];
            }
          }
          return response.blob().then(function (blob) {
            return { blob: blob, filename: filename };
          });
        })
        .then(function (data) {
          var url = window.URL.createObjectURL(data.blob);
          var a = document.createElement('a');
          a.style.display = 'none';
          a.href = url;
          a.download = data.filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        })
        .catch(function (error) {
          modules.core.toast('エクスポートに失敗しました。', 'error');
        });
    });
  }

  if (importInput) {
    importInput.addEventListener('change', function (e) {
      var file = e.target.files[0];
      if (!file) return;

      var formData = new FormData();
      formData.append('file', file);

      var roomId = modules.core.config.roomId;
      var url = '/api/task/' + encodeURIComponent(roomId) + '/import';

      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRF-Token': modules.core.csrf()
        },
        body: formData
      })
        .then(function (response) {
          return response.json().then(function (data) {
            if (!response.ok || data.status !== 'ok') {
              var errMsg = (data && data.error) ? data.error : 'インポートに失敗しました。';
              throw new Error(errMsg);
            }
            return data.data;
          });
        })
        .then(function (result) {
          var count = result.imported_count || 0;
          modules.core.toast(count + '件のタスクをインポートしました。', 'success');
          // Reload task list
          return modules.core.request(modules.core.itemsUrl(), { method: 'GET' });
        })
        .then(function (data) {
          if (data && data.items) {
            modules.store.setAll(data.items, data.tags);
          }
        })
        .catch(function (error) {
          modules.core.toast(error.message, 'error');
        })
        .finally(function () {
          importInput.value = ''; // reset
        });
    });
  }

})(window);
