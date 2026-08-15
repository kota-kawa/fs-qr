(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var dialog, form, error;
  var isNewMode = false;
  var targetNewStatus = 'todo';

  function showError(message) {
    if (!error) return;
    error.hidden = !message;
    error.textContent = message || '';
  }

  function close() {
    if (dialog && dialog.open) {
      dialog.close();
    }
  }

  function formatDate(d) {
    var year = d.getFullYear();
    var month = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  function updateAdvancedSection(hasAdvancedData) {
    var details = document.getElementById('taskEditorAdvanced');
    var badge = document.getElementById('taskEditorAdvancedBadge');
    if (details) {
      details.open = Boolean(hasAdvancedData);
    }
    if (badge) {
      badge.hidden = !hasAdvancedData;
    }
  }

  function open(item) {
    dialog = dialog || document.getElementById('taskEditorDialog');
    form = form || document.getElementById('taskEditorForm');
    error = error || document.getElementById('taskEditorError');

    isNewMode = false;
    document.getElementById('taskEditorTitle').textContent = 'タスクを編集';
    document.getElementById('taskEditorDelete').style.display = 'inline-flex';

    document.getElementById('taskEditorId').value = String(item.item_id);
    document.getElementById('taskEditorVersion').value = String(item.version);
    document.getElementById('taskEditorTitleInput').value = item.title || '';
    document.getElementById('taskEditorNote').value = item.note || '';
    document.getElementById('taskEditorDueDate').value = item.due_date || '';
    document.getElementById('taskEditorPriority').value = item.priority || 'normal';
    document.getElementById('taskEditorCategory').value = item.category || '';
    document.getElementById('taskEditorStatus').value = item.board_status || 'todo';

    var hasAdvanced = Boolean(
      (item.priority && item.priority !== 'normal') ||
      (item.due_date && String(item.due_date).trim()) ||
      (item.category && String(item.category).trim()) ||
      (item.note && String(item.note).trim())
    );
    updateAdvancedSection(hasAdvanced);

    showError('');
    if (typeof dialog.showModal === 'function') {
      dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
    document.getElementById('taskEditorTitleInput').focus();
  }

  function openCreate(initialStatus) {
    dialog = dialog || document.getElementById('taskEditorDialog');
    form = form || document.getElementById('taskEditorForm');
    error = error || document.getElementById('taskEditorError');

    isNewMode = true;
    targetNewStatus = initialStatus || 'todo';

    document.getElementById('taskEditorTitle').textContent = 'タスクを追加';
    document.getElementById('taskEditorDelete').style.display = 'none';

    document.getElementById('taskEditorId').value = '';
    document.getElementById('taskEditorVersion').value = '0';
    document.getElementById('taskEditorTitleInput').value = '';
    document.getElementById('taskEditorNote').value = '';
    document.getElementById('taskEditorDueDate').value = '';
    document.getElementById('taskEditorPriority').value = 'normal';
    document.getElementById('taskEditorCategory').value = '';
    document.getElementById('taskEditorStatus').value = targetNewStatus;

    updateAdvancedSection(false);

    showError('');
    if (typeof dialog.showModal === 'function') {
      dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
    document.getElementById('taskEditorTitleInput').focus();
  }

  async function save(event) {
    event.preventDefault();
    var title = document.getElementById('taskEditorTitleInput').value.trim();
    if (!title) {
      showError('タスク名を入力してください。');
      return;
    }

    var payload = {
      title: title,
      note: document.getElementById('taskEditorNote').value.trim(),
      due_date: document.getElementById('taskEditorDueDate').value || null,
      priority: document.getElementById('taskEditorPriority').value,
      category: document.getElementById('taskEditorCategory').value.trim(),
      board_status: document.getElementById('taskEditorStatus').value
    };

    var submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    if (isNewMode) {
      // Create new item
      try {
        var data = await core.request('/api/task/' + encodeURIComponent(core.config.roomId) + '/items', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        store.replace(data.item);
        close();
        core.toast('タスクを追加しました。', 'success');
      } catch (err) {
        showError(err.message || '追加に失敗しました。');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    } else {
      // Update existing item
      var id = Number(document.getElementById('taskEditorId').value);
      var current = store.getItem(id);
      var version = Number(document.getElementById('taskEditorVersion').value);
      payload.version = version;

      var before = store.snapshot();
      store.replace(Object.assign({}, current, payload));

      try {
        var updateData = await core.request(
          '/api/task/' + encodeURIComponent(core.config.roomId) + '/items/' + id,
          {
            method: 'PATCH',
            body: JSON.stringify(payload)
          }
        );
        store.replace(updateData.item);
        close();
        core.toast('タスクを更新しました。', 'success');
      } catch (err) {
        if (err.status === 409 && err.data && err.data.item) {
          store.replace(err.data.item);
          core.toast('他の画面で更新されました。最新の内容を表示します。', 'error');
          close();
        } else {
          store.restore(before);
          showError(err.message || '更新に失敗しました。');
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    }
  }

  async function remove() {
    var id = Number(document.getElementById('taskEditorId').value);
    var item = store.getItem(id);
    if (!item) return;

    var ok = true;
    if (window.showConfirmModal) {
      ok = await window.showConfirmModal('「' + item.title + '」を削除しますか？', {
        title: 'タスクを削除',
        confirmLabel: '削除する',
        isDanger: true
      });
    } else {
      ok = window.confirm('「' + item.title + '」を削除しますか？');
    }

    if (!ok) return;

    var before = store.snapshot();
    store.remove(id);

    try {
      await core.request(
        '/api/task/' + encodeURIComponent(core.config.roomId) + '/items/' + id,
        {
          method: 'DELETE',
          body: JSON.stringify({ version: item.version })
        }
      );
      close();
      core.toast('タスクを削除しました。', 'success');
    } catch (err) {
      store.restore(before);
      core.toast(err.message || '削除に失敗しました。', 'error');
    }
  }

  function initQuickDates() {
    document.querySelectorAll('.task-quick-date-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var dueInput = document.getElementById('taskEditorDueDate');
        if (!dueInput) return;

        if (this.dataset.dateClear === 'true') {
          dueInput.value = '';
          return;
        }

        var offset = Number(this.dataset.dateOffset || 0);
        var targetDate = new Date();
        targetDate.setDate(targetDate.getDate() + offset);
        dueInput.value = formatDate(targetDate);
      });
    });
  }

  function init() {
    dialog = document.getElementById('taskEditorDialog');
    form = document.getElementById('taskEditorForm');
    error = document.getElementById('taskEditorError');
    if (!dialog || !form) return;

    form.addEventListener('submit', save);
    document.getElementById('taskEditorClose').addEventListener('click', close);
    document.getElementById('taskEditorCancel').addEventListener('click', close);
    document.getElementById('taskEditorDelete').addEventListener('click', remove);

    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) {
        close();
      }
    });

    initQuickDates();
  }

  modules.editor = {
    init: init,
    open: open,
    openCreate: openCreate,
    close: close
  };
})(window, document);
