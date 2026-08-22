(function (window, document) {
  'use strict';

  /**
   * タグの管理（追加・名前変更・削除）と、編集ダイアログ用のタグ選択 UI。
   * タスクの分類はカテゴリではなくタグに統一しているため、分類まわりの操作は
   * このモジュールへ集約する。
   *
   * Tag management (add / rename / delete) plus the tag picker used by the task
   * editor. Classification is unified on tags, so all label handling lives here.
   */

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var dialog = null;
  var isBusy = false;

  function element(id) {
    return document.getElementById(id);
  }

  function limits() {
    return (core.config && core.config.limits) || {};
  }

  // ---------------------------------------------------------------- API 呼び出し

  async function reload() {
    var data = await core.request(core.tagsUrl(), { method: 'GET' });
    store.setTags(data.tags || []);
    return store.getTags();
  }

  /** タグを追加する。同名タグがある場合はサーバが既存タグを返す。 */
  async function createTag(name) {
    var data = await core.request(core.tagsUrl(), {
      method: 'POST',
      body: JSON.stringify({ name: name })
    });
    var tag = data.tag;
    var known = store.getTag(tag.tag_id);
    if (!known) {
      store.setTags(
        store.getTags().concat([{ tag_id: tag.tag_id, name: tag.name, item_count: 0 }])
      );
    }
    return tag;
  }

  async function renameTag(tagId, name) {
    var data = await core.request(core.tagsUrl('/' + tagId), {
      method: 'PATCH',
      body: JSON.stringify({ name: name })
    });
    store.renameTag(tagId, data.tag.name);
    return data.tag;
  }

  async function deleteTag(tagId) {
    await core.request(core.tagsUrl('/' + tagId), { method: 'DELETE' });
    store.dropTag(tagId);
    if (modules.filters) {
      modules.filters.forgetTag(tagId);
    }
  }

  // ------------------------------------------------------------------ 選択 UI

  /**
   * タグ選択チップを描画する。selectedIds は選択中のタグ ID（数値配列）で、
   * 呼び出し側がそのまま保持し続ける配列を渡す前提。
   */
  function renderPicker(container, selectedIds, options) {
    if (!container) return;
    options = options || {};
    container.textContent = '';

    var tags = store.getTags();
    if (!tags.length) {
      var empty = document.createElement('p');
      empty.className = 'task-tag-picker__empty';
      empty.textContent = core.t(
        'task.no_tags_manager',
        'タグはまだありません。下の入力欄から追加できます。'
      );
      container.appendChild(empty);
      return;
    }

    tags.forEach(function (tag) {
      var id = Number(tag.tag_id);
      var isSelected = selectedIds.indexOf(id) >= 0;
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'task-tag-chip task-tag-chip--toggle' + (isSelected ? ' is-selected' : '');
      chip.dataset.tagId = String(id);
      chip.setAttribute('aria-pressed', String(isSelected));
      chip.textContent = tag.name;
      chip.addEventListener('click', function () {
        var index = selectedIds.indexOf(id);
        if (index >= 0) {
          selectedIds.splice(index, 1);
        } else {
          var max = limits().tagsPerItem || 10;
          if (selectedIds.length >= max) {
            core.toast(
              core.formatMessage('task.tag_limit', '1つのタスクに設定できるタグは{max}件までです。', {
                max: max
              }),
              'error'
            );
            return;
          }
          selectedIds.push(id);
        }
        renderPicker(container, selectedIds, options);
        if (typeof options.onChange === 'function') {
          options.onChange(selectedIds);
        }
      });
      container.appendChild(chip);
    });
  }

  // -------------------------------------------------------------- 管理ダイアログ

  function showManagerError(message) {
    var error = element('taskTagManagerError');
    if (!error) return;
    error.hidden = !message;
    error.textContent = message || '';
  }

  function renderManagerList() {
    var list = element('taskTagManagerList');
    if (!list) return;
    list.textContent = '';

    var tags = store.getTags();
    if (!tags.length) {
      var empty = document.createElement('p');
      empty.className = 'task-tag-manager__empty';
      empty.textContent = core.t('task.no_tags', 'タグはまだありません。');
      list.appendChild(empty);
      return;
    }

    tags.forEach(function (tag) {
      list.appendChild(createManagerRow(tag));
    });
  }

  /** 1 行分（名前入力 + 保存 + 削除）を組み立てる。 */
  function createManagerRow(tag) {
    var row = document.createElement('li');
    row.className = 'task-tag-manager__row';
    row.dataset.tagId = String(tag.tag_id);

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'task-tag-manager__input';
    input.value = tag.name;
    input.maxLength = limits().tagLength || 40;
    input.setAttribute(
      'aria-label',
      core.formatMessage('task.tag_name_aria', '{name} の名前', { name: tag.name })
    );
    row.appendChild(input);

    var count = document.createElement('span');
    count.className = 'task-tag-manager__count';
    var used = Number(tag.item_count || 0);
    count.textContent = core.formatMessage('task.tag_count', '{count}', { count: used });
    count.title = core.t('task.tag_count_title', 'このタグが付いているタスク数');
    row.appendChild(count);

    var save = document.createElement('button');
    save.type = 'button';
    save.className = 'task-tag-manager__action';
    save.textContent = core.t('common.save', '保存');
    save.addEventListener('click', function () {
      applyRename(tag, input.value);
    });
    row.appendChild(save);

    input.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      applyRename(tag, input.value);
    });

    var remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'task-tag-manager__action is-danger';
    remove.textContent = core.t('common.delete', '削除');
    remove.addEventListener('click', function () {
      confirmDelete(tag);
    });
    row.appendChild(remove);

    return row;
  }

  async function applyRename(tag, rawName) {
    var name = String(rawName || '').trim();
    if (isBusy) return;
    if (!name) {
      showManagerError(core.t('task.tag_name_required', 'タグ名を入力してください。'));
      return;
    }
    if (name === tag.name) {
      showManagerError('');
      return;
    }
    isBusy = true;
    try {
      await renameTag(tag.tag_id, name);
      showManagerError('');
      renderManagerList();
      core.toast(core.t('task.tag_renamed', 'タグ名を変更しました。'), 'success');
    } catch (err) {
      showManagerError(err.message || core.t('task.tag_rename_error', 'タグ名を変更できませんでした。'));
    } finally {
      isBusy = false;
    }
  }

  async function confirmDelete(tag) {
    var used = Number(tag.item_count || 0);
    var message =
      used > 0
        ? core.formatMessage(
            'task.tag_delete_confirm_used',
            '「{name}」を削除します。{count}件のタスクからこのタグが外れます。',
            { name: tag.name, count: used }
          )
        : core.formatMessage('task.tag_delete_confirm', '「{name}」を削除しますか？', {
            name: tag.name
          });
    var ok = window.showConfirmModal
      ? await window.showConfirmModal(message, {
          title: core.t('task.tag_delete_title', 'タグを削除'),
          confirmLabel: core.t('task.delete_action', '削除する'),
          isDanger: true
        })
      : window.confirm(message);
    if (!ok || isBusy) return;

    isBusy = true;
    try {
      await deleteTag(tag.tag_id);
      showManagerError('');
      renderManagerList();
      core.toast(core.t('task.tag_deleted', 'タグを削除しました。'), 'success');
    } catch (err) {
      showManagerError(err.message || core.t('task.tag_delete_error', 'タグを削除できませんでした。'));
    } finally {
      isBusy = false;
    }
  }

  async function addFromManager() {
    var input = element('taskTagManagerInput');
    if (!input || isBusy) return;
    var name = input.value.trim();
    if (!name) {
      showManagerError(core.t('task.tag_name_required', 'タグ名を入力してください。'));
      return;
    }
    isBusy = true;
    try {
      await createTag(name);
      // 利用件数を正しく表示するため、追加後は一覧を取り直す。
      // Reload so the per-tag usage counts stay accurate.
      await reload();
      input.value = '';
      input.focus();
      showManagerError('');
      renderManagerList();
      core.toast(core.t('task.tag_added', 'タグを追加しました。'), 'success');
    } catch (err) {
      showManagerError(err.message || core.t('task.tag_add_error', 'タグを追加できませんでした。'));
    } finally {
      isBusy = false;
    }
  }

  function openManager() {
    dialog = dialog || element('taskTagManagerDialog');
    if (!dialog) return;
    showManagerError('');
    renderManagerList();
    if (typeof dialog.showModal === 'function') {
      dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
    reload()
      .then(renderManagerList)
      .catch(function () {
        // 取得できなくても、手元のタグ一覧で操作は続けられる。
        // Keep working with the cached list when the refresh fails.
      });
    var input = element('taskTagManagerInput');
    if (input) input.focus();
  }

  function closeManager() {
    if (dialog && dialog.open) {
      dialog.close();
    }
  }

  function isManagerOpen() {
    return Boolean(dialog && dialog.open);
  }

  function init() {
    dialog = element('taskTagManagerDialog');
    var openBtn = element('taskTagManagerBtn');
    if (openBtn) {
      openBtn.addEventListener('click', openManager);
    }
    if (!dialog) return;

    var closeBtn = element('taskTagManagerClose');
    if (closeBtn) closeBtn.addEventListener('click', closeManager);
    var doneBtn = element('taskTagManagerDone');
    if (doneBtn) doneBtn.addEventListener('click', closeManager);

    var addBtn = element('taskTagManagerAdd');
    if (addBtn) addBtn.addEventListener('click', addFromManager);

    var input = element('taskTagManagerInput');
    if (input) {
      input.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        addFromManager();
      });
    }

    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) closeManager();
    });
  }

  modules.tags = {
    init: init,
    reload: reload,
    createTag: createTag,
    renameTag: renameTag,
    deleteTag: deleteTag,
    renderPicker: renderPicker,
    openManager: openManager,
    closeManager: closeManager,
    isManagerOpen: isManagerOpen
  };
})(window, document);
