(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var dialog, form, error;
  var isNewMode = false;
  var isSaving = false;
  var lastFocus = null;
  var baseline = '';

  var FIELD_IDS = [
    'taskEditorTitleInput',
    'taskEditorStatus',
    'taskEditorPriority',
    'taskEditorCategory',
    'taskEditorDueDate',
    'taskEditorNote'
  ];

  function element(id) {
    return document.getElementById(id);
  }

  function showError(message) {
    if (!error) return;
    error.hidden = !message;
    error.textContent = message || '';
  }

  function snapshotForm() {
    return FIELD_IDS.map(function (id) {
      var node = element(id);
      return node ? node.value : '';
    }).join('');
  }

  function isDirty() {
    return snapshotForm() !== baseline;
  }

  function close() {
    if (dialog && dialog.open) {
      dialog.close();
    }
  }

  async function requestClose() {
    if (!isDirty()) {
      close();
      return;
    }
    var ok = window.showConfirmModal
      ? await window.showConfirmModal('編集内容が保存されていません。破棄して閉じますか？', {
          title: '変更を破棄',
          confirmLabel: '破棄する',
          isDanger: true
        })
      : window.confirm('編集内容が保存されていません。破棄して閉じますか？');
    if (ok) {
      baseline = snapshotForm();
      close();
    }
  }

  function formatDate(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, '0');
    var day = String(date.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  function setStatus(value) {
    var hidden = element('taskEditorStatus');
    if (hidden) hidden.value = value;
    document.querySelectorAll('.task-status-segment').forEach(function (segment) {
      segment.setAttribute('aria-checked', String(segment.dataset.statusValue === value));
      segment.tabIndex = segment.dataset.statusValue === value ? 0 : -1;
    });
  }

  function updateNoteCounter() {
    var note = element('taskEditorNote');
    var counter = element('taskEditorNoteCounter');
    if (!note || !counter) return;
    counter.textContent = note.value.length + ' / ' + (core.config.limits.noteLength || 500);
  }

  function updateAdvancedSection(hasAdvancedData) {
    var details = element('taskEditorAdvanced');
    var badge = element('taskEditorAdvancedBadge');
    if (details) details.open = Boolean(hasAdvancedData);
    if (badge) badge.hidden = !hasAdvancedData;
  }

  function showDialog() {
    showError('');
    baseline = snapshotForm();
    if (typeof dialog.showModal === 'function') {
      dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
    var titleInput = element('taskEditorTitleInput');
    if (titleInput) {
      titleInput.focus();
      titleInput.select();
    }
  }

  function ensureRefs() {
    dialog = dialog || element('taskEditorDialog');
    form = form || element('taskEditorForm');
    error = error || element('taskEditorError');
  }

  function open(item) {
    ensureRefs();
    lastFocus = document.activeElement;
    isNewMode = false;

    element('taskEditorTitle').textContent = 'タスクを編集';
    element('taskEditorDelete').style.display = 'inline-flex';

    element('taskEditorId').value = String(item.item_id);
    element('taskEditorVersion').value = String(item.version);
    element('taskEditorTitleInput').value = item.title || '';
    element('taskEditorNote').value = item.note || '';
    element('taskEditorDueDate').value = item.due_date || '';
    element('taskEditorPriority').value = item.priority || 'normal';
    if (modules.select) {
      modules.select.sync(element('taskEditorPriority'));
    }
    element('taskEditorCategory').value = item.category || '';
    setStatus(item.board_status || 'todo');
    updateNoteCounter();

    updateAdvancedSection(
      Boolean(
        (item.priority && item.priority !== 'normal') ||
          (item.due_date && String(item.due_date).trim()) ||
          (item.category && String(item.category).trim()) ||
          (item.note && String(item.note).trim())
      )
    );

    showDialog();
  }

  /**
   * Open the dialog in creation mode.
   * options.dueDate を渡すと、期限日を事前入力した状態で開く（カレンダー用）。
   */
  function openCreate(initialStatus, options) {
    ensureRefs();
    lastFocus = document.activeElement;
    isNewMode = true;

    var dueDate = (options && options.dueDate) || '';

    element('taskEditorTitle').textContent = 'タスクを追加';
    element('taskEditorDelete').style.display = 'none';

    element('taskEditorId').value = '';
    element('taskEditorVersion').value = '0';
    element('taskEditorTitleInput').value = '';
    element('taskEditorNote').value = '';
    element('taskEditorDueDate').value = dueDate;
    element('taskEditorPriority').value = 'normal';
    if (modules.select) {
      modules.select.sync(element('taskEditorPriority'));
    }
    element('taskEditorCategory').value = '';
    setStatus(initialStatus || 'todo');
    updateNoteCounter();
    updateAdvancedSection(Boolean(dueDate));

    showDialog();
  }

  function collectPayload() {
    return {
      title: element('taskEditorTitleInput').value.trim(),
      note: element('taskEditorNote').value.trim(),
      due_date: element('taskEditorDueDate').value || null,
      priority: element('taskEditorPriority').value,
      category: element('taskEditorCategory').value.trim(),
      board_status: element('taskEditorStatus').value
    };
  }

  async function save(event) {
    if (event) event.preventDefault();
    if (isSaving) return;

    var payload = collectPayload();
    if (!payload.title) {
      showError('タスク名を入力してください。');
      element('taskEditorTitleInput').focus();
      return;
    }

    var submitBtn = form.querySelector('button[type="submit"]');
    isSaving = true;
    if (submitBtn) submitBtn.disabled = true;

    if (isNewMode) {
      try {
        await modules.actions.createItem(payload);
        baseline = snapshotForm();
        close();
        core.toast('タスクを追加しました。', 'success');
      } catch (err) {
        showError(err.message || '追加に失敗しました。');
      } finally {
        isSaving = false;
        if (submitBtn) submitBtn.disabled = false;
      }
      return;
    }

    var id = Number(element('taskEditorId').value);
    var current = store.getItem(id);
    payload.version = Number(element('taskEditorVersion').value);

    var before = store.snapshot();
    store.replace(Object.assign({}, current, payload));

    try {
      var updated = await core.request(core.itemsUrl('/' + id), {
        method: 'PATCH',
        body: JSON.stringify(payload)
      });
      store.replace(updated.item);
      baseline = snapshotForm();
      close();
      core.toast('タスクを更新しました。', 'success');
    } catch (err) {
      if (err.status === 409 && err.data && err.data.item) {
        store.replace(err.data.item);
        core.toast('他の画面で更新されました。最新の内容を表示します。', 'error');
        baseline = snapshotForm();
        close();
      } else {
        store.restore(before);
        showError(err.message || '更新に失敗しました。');
      }
    } finally {
      isSaving = false;
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  async function removeCurrent() {
    var id = Number(element('taskEditorId').value);
    if (!store.getItem(id)) return;
    var deleted = await modules.actions.deleteItem(id);
    if (deleted) {
      baseline = snapshotForm();
      close();
    }
  }

  function initQuickDates() {
    document.querySelectorAll('.task-quick-date-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        var dueInput = element('taskEditorDueDate');
        if (!dueInput) return;

        if (this.dataset.dateClear === 'true') {
          dueInput.value = '';
          return;
        }
        var target = new Date();
        target.setDate(target.getDate() + Number(this.dataset.dateOffset || 0));
        dueInput.value = formatDate(target);
      });
    });
  }

  function initStatusSegments() {
    var segments = Array.prototype.slice.call(document.querySelectorAll('.task-status-segment'));
    segments.forEach(function (segment, index) {
      segment.addEventListener('click', function () {
        setStatus(segment.dataset.statusValue);
      });
      segment.addEventListener('keydown', function (event) {
        if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
        event.preventDefault();
        var offset = event.key === 'ArrowRight' ? 1 : -1;
        var next = segments[(index + offset + segments.length) % segments.length];
        setStatus(next.dataset.statusValue);
        next.focus();
      });
    });
  }

  function init() {
    ensureRefs();
    if (!dialog || !form) return;

    form.addEventListener('submit', save);
    element('taskEditorClose').addEventListener('click', requestClose);
    element('taskEditorCancel').addEventListener('click', requestClose);
    element('taskEditorDelete').addEventListener('click', removeCurrent);

    var note = element('taskEditorNote');
    if (note) note.addEventListener('input', updateNoteCounter);

    // Ctrl/Cmd + Enter saves from any field. / どの入力欄からでも保存できる。
    form.addEventListener('keydown', function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        if (event.repeat) return;
        save();
      }
    });

    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) {
        requestClose();
      }
    });

    dialog.addEventListener('cancel', function (event) {
      if (isDirty()) {
        event.preventDefault();
        requestClose();
      }
    });

    dialog.addEventListener('close', function () {
      if (lastFocus && document.contains(lastFocus)) {
        lastFocus.focus();
      }
      lastFocus = null;
    });

    initQuickDates();
    initStatusSegments();
  }

  modules.editor = {
    init: init,
    open: open,
    openCreate: openCreate,
    close: close,
    isOpen: function () {
      return Boolean(dialog && dialog.open);
    }
  };
})(window, document);
