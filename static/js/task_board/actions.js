(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  function announce(message) {
    if (modules.render && modules.render.announce) {
      modules.render.announce(message);
    }
  }

  function conflictMessage(err) {
    return err.status === 409
      ? core.t('task.conflict_short', '他の画面で更新されました。')
      : (err.message || core.t('task.update_error', '更新に失敗しました。'));
  }

  /** Items of one column in board order. / カラム内のタスクを表示順で取得する。 */
  function ordered(status) {
    return store
      .getItems()
      .filter(function (item) {
        return item.board_status === status;
      })
      .sort(function (a, b) {
        return a.position - b.position || a.item_id - b.item_id;
      });
  }

  async function persistMove(item, status, position, needReorder, orderedItemIds) {
    var before = store.snapshot();
    var changed = Object.assign({}, item, { board_status: status, position: position });
    var moveCommitted = false;
    store.replace(changed);

    try {
      if (needReorder) {
        // A cross-column item must exist in the destination on the server before
        // the reorder endpoint can validate the complete destination ID set.
        // 別カラムへの移動時は、並び替えAPIの集合検証より先に移動を確定する。
        if (item.board_status !== status) {
          var moved = await core.request(core.itemsUrl('/' + item.item_id), {
            method: 'PATCH',
            body: JSON.stringify({
              version: item.version,
              board_status: status,
              position: position
            })
          });
          moveCommitted = true;
          store.replace(moved.item);
        }

        // Position space collapsed: rewrite the whole column in the intended order.
        // 位置の隙間が無くなったので、意図した順序でカラム全体を振り直す。
        var reorderData = await core.request(core.itemsUrl('/reorder'), {
          method: 'POST',
          body: JSON.stringify({ board_status: status, ordered_item_ids: orderedItemIds })
        });
        (reorderData.items || []).forEach(function (updated) {
          store.replace(updated);
        });
        announce(
          core.formatMessage('task.item_moved', '「{title}」を{status}へ移動しました', {
            title: changed.title,
            status: core.statusLabel(status)
          })
        );
      } else {
        var data = await core.request(core.itemsUrl('/' + item.item_id), {
          method: 'PATCH',
          body: JSON.stringify({
            version: item.version,
            board_status: status,
            position: position
          })
        });
        store.replace(data.item);
        announce(
          core.formatMessage('task.item_moved', '「{title}」を{status}へ移動しました', {
            title: data.item.title,
            status: core.statusLabel(status)
          })
        );
      }
    } catch (err) {
      if (err.status === 409 && err.data && err.data.item) {
        store.replace(err.data.item);
      } else if (moveCommitted) {
        // The move succeeded but normalization failed. Re-sync instead of
        // restoring a snapshot that no longer matches the server.
        // 移動後の並び替えだけ失敗した場合は、古い状態へ戻さず再同期する。
        try {
          var latest = await core.request(core.itemsUrl(), { method: 'GET' });
          store.setAll(latest.items, latest.tags);
        } catch (syncError) {
          // The regular poll will retry synchronization.
          // 通常ポーリングで再同期を再試行する。
        }
      } else {
        store.restore(before);
      }
      core.toast(
        err.status === 409
          ? core.t('task.conflict_short', '他の画面で更新されました。')
          : (err.message || core.t('task.move_error', '移動に失敗しました。')),
        'error'
      );
    }
  }

  /** Move an item to targetIndex of targetStatus. / 指定位置へタスクを移動する。 */
  function moveBy(item, targetStatus, targetIndex) {
    var next = ordered(targetStatus).filter(function (candidate) {
      return candidate.item_id !== item.item_id;
    });

    var index = Math.max(0, Math.min(targetIndex, next.length));
    next.splice(index, 0, item);

    var previous = next[index - 1];
    var following = next[index + 1];
    var position;
    var needReorder = false;

    if (previous && following) {
      var gap = following.position - previous.position;
      if (gap <= 1) {
        needReorder = true;
        position = previous.position + 1;
      } else {
        position = Math.floor((previous.position + following.position) / 2);
      }
    } else if (previous) {
      position = previous.position + 100;
    } else if (following) {
      if (following.position <= 1) {
        needReorder = true;
        position = 0;
      } else {
        position = Math.max(0, Math.floor(following.position / 2));
      }
    } else {
      position = 100;
    }

    persistMove(
      item,
      targetStatus,
      position,
      needReorder,
      next.map(function (candidate) {
        return candidate.item_id;
      })
    );
  }

  function moveToColumn(item, status) {
    moveBy(item, status, ordered(status).length);
  }

  function moveWithin(item, offset) {
    var list = ordered(item.board_status);
    var index = list.findIndex(function (candidate) {
      return candidate.item_id === item.item_id;
    });
    if (index < 0) return;
    moveBy(item, item.board_status, Math.max(0, index + offset));
  }

  /** Create a task and merge it into the store. / タスクを作成してストアへ反映する。 */
  async function createItem(fields) {
    if (store.getItems().length >= core.config.limits.maxItems) {
      var limitError = new Error(
        core.formatMessage(
          'task.limit_reached',
          'タスク数の上限（{max}件）に達しました。',
          { max: core.config.limits.maxItems }
        )
      );
      limitError.isLimit = true;
      throw limitError;
    }
    var data = await core.request(core.itemsUrl(), {
      method: 'POST',
      body: JSON.stringify(
        Object.assign(
          {
            title: '',
            note: '',
            priority: 'normal',
            tag_ids: [],
            due_date: null,
            board_status: 'todo'
          },
          fields || {}
        )
      )
    });
    store.replace(data.item);
    announce(
      core.formatMessage('task.item_added', '「{title}」を追加しました', {
        title: data.item.title
      })
    );
    return data.item;
  }

  async function toggleDone(itemId) {
    var item = store.getItem(itemId);
    if (!item) return;

    var before = store.snapshot();
    var status = item.board_status === 'done' ? 'todo' : 'done';
    store.replace(Object.assign({}, item, { board_status: status }));

    try {
      var data = await core.request(core.itemsUrl('/' + item.item_id), {
        method: 'PATCH',
        body: JSON.stringify({ version: item.version, board_status: status })
      });
      store.replace(data.item);
      announce(
        core.formatMessage('task.status_changed', '「{title}」を{status}にしました', {
          title: item.title,
          status: core.statusLabel(status)
        })
      );
    } catch (err) {
      if (err.status === 409 && err.data && err.data.item) {
        store.replace(err.data.item);
      } else {
        store.restore(before);
      }
      core.toast(conflictMessage(err), 'error');
    }
  }

  /**
   * Change only the due date of a task (calendar drag & drop).
   * 期限日だけを更新する。カレンダーのドラッグ＆ドロップで使う。
   */
  async function setDueDate(itemId, dueDate) {
    var item = store.getItem(itemId);
    if (!item) return;

    var next = dueDate || null;
    if ((item.due_date || null) === next) return;

    var before = store.snapshot();
    store.replace(Object.assign({}, item, { due_date: next }));

    try {
      var data = await core.request(core.itemsUrl('/' + item.item_id), {
        method: 'PATCH',
        body: JSON.stringify({ version: item.version, due_date: next })
      });
      store.replace(data.item);
      announce(
        next
          ? core.formatMessage('task.due_changed', '「{title}」の期限を{date}に変更しました', {
              title: data.item.title,
              date: next
            })
          : core.formatMessage('task.due_cleared', '「{title}」の期限を解除しました', {
              title: data.item.title
            })
      );
    } catch (err) {
      if (err.status === 409 && err.data && err.data.item) {
        store.replace(err.data.item);
      } else {
        store.restore(before);
      }
      core.toast(conflictMessage(err), 'error');
    }
  }

  function payloadOf(item) {
    return {
      title: item.title,
      note: item.note || '',
      priority: item.priority || 'normal',
      // 復元は名前で行う。取り消しまでの間にタグが消えても付け直せる。
      // Undo restores tags by name so a tag deleted meanwhile is recreated.
      tags: (item.tags || []).map(function (tag) {
        return tag.name;
      }),
      start_date: item.start_date || null,
      due_date: item.due_date || null,
      board_status: item.board_status || 'todo'
    };
  }

  /** Re-create previously deleted items (undo support). / 削除の取り消し。 */
  async function restoreItems(snapshots) {
    var failed = 0;
    for (var index = 0; index < snapshots.length; index += 1) {
      try {
        var data = await core.request(core.itemsUrl(), {
          method: 'POST',
          body: JSON.stringify(payloadOf(snapshots[index]))
        });
        store.replace(data.item);
      } catch (err) {
        failed += 1;
      }
    }
    if (failed > 0) {
      core.toast(
        core.formatMessage('task.restore_failed', '{count}件のタスクを復元できませんでした。', {
          count: failed
        }),
        'error'
      );
    } else {
      core.toast(core.t('task.restored', 'タスクを復元しました。'), 'success');
    }
  }

  async function confirmDialog(message, title) {
    if (window.showConfirmModal) {
      return window.showConfirmModal(message, {
        title: title || core.t('task.delete_title', 'タスクを削除'),
        confirmLabel: core.t('task.delete_action', '削除する'),
        isDanger: true
      });
    }
    return window.confirm(message);
  }

  async function deleteItem(itemId, options) {
    var item = store.getItem(itemId);
    if (!item) return false;

    if (!(options && options.skipConfirm)) {
      var ok = await confirmDialog(
        core.formatMessage('task.delete_confirm', '「{title}」を削除しますか？', {
          title: item.title
        })
      );
      if (!ok) return false;
    }

    var before = store.snapshot();
    var backup = JSON.parse(JSON.stringify(item));
    store.remove(itemId);

    try {
      await core.request(core.itemsUrl('/' + item.item_id), {
        method: 'DELETE',
        body: JSON.stringify({ version: item.version })
      });
      announce(
        core.formatMessage('task.deleted_item', '「{title}」を削除しました', {
          title: backup.title
        })
      );
      core.toastWithUndo(core.t('task.deleted', 'タスクを削除しました。'), function () {
        restoreItems([backup]);
      });
      return true;
    } catch (err) {
      store.restore(before);
      core.toast(err.message || core.t('task.delete_failed', '削除に失敗しました。'), 'error');
      return false;
    }
  }

  /** Delete every finished task at once. / 完了タスクの一括削除。 */
  async function clearDone() {
    var doneItems = store.getItems().filter(function (item) {
      return item.board_status === 'done';
    });
    if (doneItems.length === 0) {
      core.toast(core.t('task.no_completed', '完了したタスクはありません。'), 'info');
      return;
    }

    var ok = await confirmDialog(
      core.formatMessage(
        'task.bulk_delete_confirm',
        '完了した{count}件のタスクを削除しますか？',
        { count: doneItems.length }
      ),
      core.t('task.bulk_delete_title', '完了タスクの一括削除')
    );
    if (!ok) return;

    var before = store.snapshot();
    var backups = JSON.parse(JSON.stringify(doneItems));
    store.removeMany(
      doneItems.map(function (item) {
        return item.item_id;
      })
    );

    var failed = [];
    for (var index = 0; index < doneItems.length; index += 1) {
      try {
        await core.request(core.itemsUrl('/' + doneItems[index].item_id), {
          method: 'DELETE',
          body: JSON.stringify({ version: doneItems[index].version })
        });
      } catch (err) {
        failed.push(doneItems[index]);
      }
    }

    if (failed.length === doneItems.length) {
      store.restore(before);
      core.toast(core.t('task.bulk_delete_failed', '完了タスクを削除できませんでした。'), 'error');
      return;
    }

    // Restore only the items whose server deletion failed.
    // サーバーで削除できなかった項目だけを画面へ戻す。
    failed.forEach(function (item) {
      store.replace(item);
    });

    var deleted = backups.filter(function (backup) {
      return !failed.some(function (item) {
        return item.item_id === backup.item_id;
      });
    });
    announce(
      core.formatMessage('task.bulk_deleted', '{count}件の完了タスクを削除しました', {
        count: deleted.length
      })
    );
    core.toastWithUndo(
      core.formatMessage('task.bulk_deleted', '{count}件の完了タスクを削除しました。', {
        count: deleted.length
      }),
      function () {
        restoreItems(deleted);
      }
    );
    if (failed.length > 0) {
      core.toast(
        core.formatMessage('task.bulk_delete_partial', '{count}件のタスクを削除できませんでした。', {
          count: failed.length
        }),
        'error'
      );
    }
  }

  /** Contextual menu shown from a card's ⋮ button. / カードの操作メニュー。 */
  function openCardMenu(anchor, card) {
    var item = store.getItem(card.dataset.itemId);
    if (!item || !modules.menu) return;

    var currentList = ordered(item.board_status);
    var currentIndex = currentList.findIndex(function (candidate) {
      return candidate.item_id === item.item_id;
    });
    var customOrder = !modules.filters || modules.filters.isCustomOrder();

    var entries = [
      {
        label: core.t('task.edit_details', '詳細・編集'),
        icon: 'edit',
        onSelect: function () {
          var now = store.getItem(item.item_id);
          if (now && modules.editor) modules.editor.open(now);
        }
      },
      { divider: true }
    ];

    core.STATUSES.forEach(function (status) {
      if (status === item.board_status) return;
      entries.push({
        label: core.formatMessage('task.move_to', '{status}へ移動', {
          status: core.statusLabel(status)
        }),
        icon: status === 'todo' ? 'arrowLeft' : (status === 'done' ? 'arrowRight' : 'arrowRight'),
        onSelect: function () {
          var now = store.getItem(item.item_id);
          if (now) moveToColumn(now, status);
        }
      });
    });

    entries.push({ divider: true });
    entries.push({
      label: core.t('task.move_up', '上へ移動'),
      icon: 'arrowUp',
      disabled: !customOrder || currentIndex <= 0,
      onSelect: function () {
        var now = store.getItem(item.item_id);
        if (now) moveWithin(now, -1);
      }
    });
    entries.push({
      label: core.t('task.move_down', '下へ移動'),
      icon: 'arrowDown',
      disabled: !customOrder || currentIndex < 0 || currentIndex >= currentList.length - 1,
      onSelect: function () {
        var now = store.getItem(item.item_id);
        if (now) moveWithin(now, 1);
      }
    });
    entries.push({ divider: true });
    entries.push({
      label: core.t('task.delete', '削除'),
      icon: 'trash',
      danger: true,
      onSelect: function () {
        deleteItem(item.item_id);
      }
    });

    modules.menu.open(anchor, entries);
  }

  /** Column header menu. / カラムヘッダーの操作メニュー。 */
  function openColumnMenu(anchor, status) {
    if (!modules.menu) return;
    var column = anchor.closest('.task-column');
    var collapsed = column && column.classList.contains('is-collapsed');

    var entries = [
      {
        label: core.t('task.column_add', 'このカラムに追加'),
        icon: 'plus',
        onSelect: function () {
          if (modules.columns) modules.columns.openInlineAdd(status);
        }
      },
      {
        label: collapsed
          ? core.t('task.column_expand', 'カラムを展開')
          : core.t('task.column_collapse', 'カラムを折りたたむ'),
        icon: 'collapse',
        onSelect: function () {
          if (modules.columns) modules.columns.toggleCollapse(status);
        }
      }
    ];

    if (status === 'done') {
      entries.push({ divider: true });
      entries.push({
        label: core.t('task.bulk_delete_action', '完了タスクを一括削除'),
        icon: 'broom',
        danger: true,
        onSelect: clearDone
      });
    }

    modules.menu.open(anchor, entries);
  }

  modules.actions = {
    ordered: ordered,
    createItem: createItem,
    moveBy: moveBy,
    moveToColumn: moveToColumn,
    moveWithin: moveWithin,
    toggleDone: toggleDone,
    setDueDate: setDueDate,
    deleteItem: deleteItem,
    clearDone: clearDone,
    restoreItems: restoreItems,
    openCardMenu: openCardMenu,
    openColumnMenu: openColumnMenu
  };
})(window, document);
