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
  // 編集中のタスクに付けるタグ（タグ ID の配列）。分類はタグに統一している。
  // Tag ids selected for the task being edited; classification is tag-only.
  var selectedTagIds = [];

  var FIELD_IDS = [
    'taskEditorTitleInput',
    'taskEditorStatus',
    'taskEditorPriority',
    'taskEditorStartDate',
    'taskEditorDueDate',
    'taskEditorNote'
  ];

  function element(id) {
    return document.getElementById(id);
  }

  /** タグ選択チップを描き直す。 / Re-render the tag picker chips. */
  function renderTagPicker() {
    if (!modules.tags) return;
    modules.tags.renderPicker(element('taskEditorTags'), selectedTagIds, {
      onChange: updateTagCounter
    });
    updateTagCounter();
  }

  function updateTagCounter() {
    var counter = element('taskEditorTagCounter');
    if (!counter) return;
    var max = (core.config.limits && core.config.limits.tagsPerItem) || 10;
    counter.textContent = selectedTagIds.length + ' / ' + max;
  }

  function showError(message) {
    if (!error) return;
    error.hidden = !message;
    error.textContent = message || '';
  }

  function snapshotForm() {
    // タグの選択も未保存の変更として扱う。 / Tag selection counts as a change too.
    return FIELD_IDS.map(function (id) {
      var node = element(id);
      return node ? node.value : '';
    })
      .concat(selectedTagIds.slice().sort().join(','))
      .join('');
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
      ? await window.showConfirmModal(core.t('task.unsaved_confirm', '編集内容が保存されていません。破棄して閉じますか？'), {
          title: core.t('task.discard_title', '変更を破棄'),
          confirmLabel: core.t('task.discard_action', '破棄する'),
          isDanger: true
        })
      : window.confirm(core.t('task.unsaved_confirm', '編集内容が保存されていません。破棄して閉じますか？'));
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

    element('taskEditorTitle').textContent = core.t('task.edit_title', 'タスクを編集');
    element('taskEditorDelete').style.display = 'inline-flex';

    element('taskEditorId').value = String(item.item_id);
    element('taskEditorVersion').value = String(item.version);
    element('taskEditorTitleInput').value = item.title || '';
    element('taskEditorNote').value = item.note || '';
    element('taskEditorStartDate').value = item.start_date || '';
    element('taskEditorDueDate').value = item.due_date || '';
    element('taskEditorPriority').value = item.priority || 'normal';
    if (modules.select) {
      modules.select.sync(element('taskEditorPriority'));
    }
    selectedTagIds = store.tagIdsOf(item);
    renderTagPicker();
    setStatus(item.board_status || 'todo');
    updateNoteCounter();

    updateAdvancedSection(
      Boolean(
        (item.priority && item.priority !== 'normal') ||
          (item.start_date && String(item.start_date).trim()) ||
          (item.due_date && String(item.due_date).trim()) ||
          selectedTagIds.length ||
          (item.note && String(item.note).trim())
      )
    );

    showDialog();
  }

  /**
   * Open the dialog in creation mode.
   * options.dueDate を渡すと、期限日を事前入力した状態で開く（カレンダー用）。
   * 未指定時は開始日・締切日ともに今日の日付をデフォルトで入力する。
   */
  function openCreate(initialStatus, options) {
    ensureRefs();
    lastFocus = document.activeElement;
    isNewMode = true;

    // 新規作成時は開始日・締切日を今日の日付（クライアントのローカル日付）でデフォルト初期化する。
    // カレンダーから明示的な締切日が渡された場合はそれを優先しつつ、
    // 開始日は締切日が今日以降のときだけ今日をデフォルトにして日付範囲の矛盾（開始日 > 締切日）を避ける。
    var todayStr = formatDate(new Date());
    var dueDate = (options && options.dueDate) || todayStr;
    var startDate = dueDate >= todayStr ? todayStr : '';

    element('taskEditorTitle').textContent = core.t('task.add_title', 'タスクを追加');
    element('taskEditorDelete').style.display = 'none';

    element('taskEditorId').value = '';
    element('taskEditorVersion').value = '0';
    element('taskEditorTitleInput').value = '';
    element('taskEditorNote').value = '';
    element('taskEditorStartDate').value = startDate;
    element('taskEditorDueDate').value = dueDate;
    element('taskEditorPriority').value = 'normal';
    if (modules.select) {
      modules.select.sync(element('taskEditorPriority'));
    }
    selectedTagIds = [];
    renderTagPicker();
    setStatus(initialStatus || 'todo');
    updateNoteCounter();
    updateAdvancedSection(Boolean(startDate || dueDate));

    showDialog();
  }

  function collectPayload() {
    return {
      title: element('taskEditorTitleInput').value.trim(),
      note: element('taskEditorNote').value.trim(),
      start_date: element('taskEditorStartDate').value || null,
      due_date: element('taskEditorDueDate').value || null,
      priority: element('taskEditorPriority').value,
      tag_ids: selectedTagIds.slice(),
      board_status: element('taskEditorStatus').value
    };
  }

  /** タグ ID から表示用のタグ情報へ戻す。 / Map tag ids back to tag objects. */
  function tagsOf(tagIds) {
    return (tagIds || [])
      .map(function (id) {
        return store.getTag(id);
      })
      .filter(Boolean)
      .map(function (tag) {
        return { tag_id: Number(tag.tag_id), name: tag.name };
      });
  }

  async function save(event) {
    if (event) event.preventDefault();
    if (isSaving) return;

    var payload = collectPayload();
    if (!payload.title) {
      showError(core.t('task.name_required', 'タスク名を入力してください。'));
      element('taskEditorTitleInput').focus();
      return;
    }
    if (payload.start_date && payload.due_date) {
      if (payload.start_date > payload.due_date) {
        showError(core.t('task.start_before_due', '開始日は期限日以前の日付を指定してください。'));
        return;
      }
    }

    var submitBtn = form.querySelector('button[type="submit"]');
    isSaving = true;
    if (submitBtn) submitBtn.disabled = true;

    if (isNewMode) {
      try {
        await modules.actions.createItem(payload);
        baseline = snapshotForm();
        close();
        core.toast(core.t('task.added', 'タスクを追加しました。'), 'success');
      } catch (err) {
        showError(err.message || core.t('task.add_error', '追加に失敗しました。'));
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
    store.replace(Object.assign({}, current, payload, { tags: tagsOf(payload.tag_ids) }));

    try {
      var updated = await core.request(core.itemsUrl('/' + id), {
        method: 'PATCH',
        body: JSON.stringify(payload)
      });
      store.replace(updated.item);
      baseline = snapshotForm();
      close();
      core.toast(core.t('task.updated', 'タスクを更新しました。'), 'success');
    } catch (err) {
      if (err.status === 409 && err.data && err.data.item) {
        store.replace(err.data.item);
        core.toast(core.t('task.conflict_detail', '他の画面で更新されました。最新の内容を表示します。'), 'error');
        baseline = snapshotForm();
        close();
      } else {
        store.restore(before);
        showError(err.message || core.t('task.update_error', '更新に失敗しました。'));
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

  /**
   * 編集ダイアログからタグを新規追加する。追加したタグはそのまま選択状態にする。
   * Adds a tag straight from the editor and selects it for the current task.
   */
  async function addTagFromEditor() {
    var input = element('taskEditorTagInput');
    if (!input || !modules.tags) return;
    var name = input.value.trim();
    if (!name) return;

    var max = (core.config.limits && core.config.limits.tagsPerItem) || 10;
    if (selectedTagIds.length >= max) {
      showError(
        core.formatMessage('task.tag_limit', '1つのタスクに設定できるタグは{max}件までです。', {
          max: max
        })
      );
      return;
    }

    try {
      var tag = await modules.tags.createTag(name);
      var id = Number(tag.tag_id);
      if (selectedTagIds.indexOf(id) < 0) {
        selectedTagIds.push(id);
      }
      input.value = '';
      input.focus();
      showError('');
      renderTagPicker();
    } catch (err) {
      showError(err.message || core.t('task.tag_add_error', 'タグを追加できませんでした。'));
    }
  }

  function initTagControls() {
    var addBtn = element('taskEditorTagAdd');
    if (addBtn) {
      addBtn.addEventListener('click', addTagFromEditor);
    }
    var input = element('taskEditorTagInput');
    if (input) {
      // Enter でフォーム送信されないよう、ここでタグ追加として処理する。
      // Enter adds a tag instead of submitting the whole editor form.
      input.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        addTagFromEditor();
      });
    }
    var manageBtn = element('taskEditorTagManage');
    if (manageBtn && modules.tags) {
      manageBtn.addEventListener('click', function () {
        modules.tags.openManager();
      });
    }
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
    initTagControls();

    // タグの追加・改名・削除を編集画面のチップへ反映する。
    // Keep the picker in sync with tag add / rename / delete.
    store.subscribe(function () {
      if (dialog && dialog.open) {
        renderTagPicker();
      }
    });
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
