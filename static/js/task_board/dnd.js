(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var dragging = null;
  var ghost = null;
  var start = null;
  var activePointerId = null;
  var currentDragOverList = null;

  var labels = {
    todo: '未着手',
    doing: '進行中',
    done: '完了'
  };

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

  function announce(item, status) {
    if (modules.render && modules.render.announce) {
      modules.render.announce('「' + item.title + '」を' + (labels[status] || status) + 'へ移動しました');
    }
  }

  async function persist(item, status, position, needReorder) {
    var before = store.snapshot();
    var changed = Object.assign({}, item, { board_status: status, position: position });
    store.replace(changed);

    try {
      if (needReorder) {
        // Position space collapsed: do clean column reorder
        var list = ordered(status).map(function (c) {
          return c.item_id;
        });
        var reorderData = await core.request(
          '/api/task/' + encodeURIComponent(core.config.roomId) + '/items/reorder',
          {
            method: 'POST',
            body: JSON.stringify({ board_status: status, ordered_item_ids: list })
          }
        );
        (reorderData.items || []).forEach(function (updated) {
          store.replace(updated);
        });
        announce(changed, status);
      } else {
        // Single fast PATCH
        var data = await core.request(
          '/api/task/' + encodeURIComponent(core.config.roomId) + '/items/' + item.item_id,
          {
            method: 'PATCH',
            body: JSON.stringify({
              version: item.version,
              board_status: status,
              position: position
            })
          }
        );
        store.replace(data.item);
        announce(data.item, status);
      }
    } catch (err) {
      if (err.status === 409 && err.data && err.data.item) {
        store.replace(err.data.item);
      } else {
        store.restore(before);
      }
      core.toast(
        err.status === 409
          ? '他の画面で更新されました。'
          : (err.message || '移動に失敗しました。'),
        'error'
      );
    }
  }

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

    persist(item, targetStatus, position, needReorder);
  }

  function openMenu(card) {
    document.querySelectorAll('.task-card__move-menu').forEach(function (menu) {
      menu.remove();
    });

    var item = store.getItem(card.dataset.itemId);
    if (!item) return;

    var menu = document.createElement('div');
    menu.className = 'task-card__move-menu';
    menu.setAttribute('role', 'menu');

    var currentList = ordered(item.board_status);
    var currentIndex = currentList.findIndex(function (c) {
      return c.item_id === item.item_id;
    });

    // Move to different columns
    ['todo', 'doing', 'done'].forEach(function (st) {
      if (st === item.board_status) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = (labels[st] || st) + 'へ移動';
      btn.addEventListener('click', function () {
        var now = store.getItem(item.item_id);
        if (now) {
          moveBy(now, st, ordered(st).length);
        }
        menu.remove();
      });
      menu.appendChild(btn);
    });

    // Reorder within column (Up / Down)
    if (currentIndex > 0) {
      var upBtn = document.createElement('button');
      upBtn.type = 'button';
      upBtn.textContent = '上へ移動';
      upBtn.addEventListener('click', function () {
        var now = store.getItem(item.item_id);
        if (now) {
          var list = ordered(now.board_status);
          var idx = list.findIndex(function (c) {
            return c.item_id === now.item_id;
          });
          moveBy(now, now.board_status, Math.max(0, idx - 1));
        }
        menu.remove();
      });
      menu.appendChild(upBtn);
    }

    if (currentIndex < currentList.length - 1) {
      var downBtn = document.createElement('button');
      downBtn.type = 'button';
      downBtn.textContent = '下へ移動';
      downBtn.addEventListener('click', function () {
        var now = store.getItem(item.item_id);
        if (now) {
          var list = ordered(now.board_status);
          var idx = list.findIndex(function (c) {
            return c.item_id === now.item_id;
          });
          // Fix: index + 1 moves immediately past next element
          moveBy(now, now.board_status, idx + 1);
        }
        menu.remove();
      });
      menu.appendChild(downBtn);
    }

    var divider = document.createElement('div');
    divider.className = 'task-card__move-menu-divider';
    menu.appendChild(divider);

    // Edit button
    var editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.textContent = '詳細・編集';
    editBtn.addEventListener('click', function () {
      var now = store.getItem(item.item_id);
      if (now && modules.editor) {
        modules.editor.open(now);
      }
      menu.remove();
    });
    menu.appendChild(editBtn);

    // Delete button
    var delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'is-danger';
    delBtn.textContent = '削除';
    delBtn.addEventListener('click', async function () {
      menu.remove();
      var now = store.getItem(item.item_id);
      if (!now) return;

      var ok = true;
      if (window.showConfirmModal) {
        ok = await window.showConfirmModal('「' + now.title + '」を削除しますか？', {
          title: 'タスクを削除',
          confirmLabel: '削除する',
          isDanger: true
        });
      } else {
        ok = window.confirm('「' + now.title + '」を削除しますか？');
      }

      if (!ok) return;

      var before = store.snapshot();
      store.remove(now.item_id);

      try {
        await core.request(
          '/api/task/' + encodeURIComponent(core.config.roomId) + '/items/' + now.item_id,
          {
            method: 'DELETE',
            body: JSON.stringify({ version: now.version })
          }
        );
        core.toast('タスクを削除しました。', 'success');
      } catch (err) {
        store.restore(before);
        core.toast(err.message || '削除に失敗しました。', 'error');
      }
    });
    menu.appendChild(delBtn);

    card.appendChild(menu);
  }

  function clearDragOverHighlights() {
    document.querySelectorAll('.task-column__list.is-drag-over').forEach(function (el) {
      el.classList.remove('is-drag-over');
    });
    currentDragOverList = null;
  }

  function onPointerDown(event) {
    var handle = event.target.closest('.task-card__drag-handle');
    if (!handle || event.button !== 0) return;

    var card = handle.closest('.task-card');
    if (!card) return;

    start = {
      x: event.clientX,
      y: event.clientY,
      card: card,
      handle: handle
    };
    activePointerId = event.pointerId;
  }

  function onPointerMove(event) {
    if (!start) return;

    if (!dragging && Math.hypot(event.clientX - start.x, event.clientY - start.y) < 8) {
      return;
    }

    if (!dragging) {
      dragging = start.card;
      dragging.classList.add('is-dragging');
      ghost = dragging.cloneNode(true);
      ghost.classList.add('task-card--ghost');
      document.body.appendChild(ghost);

      if (start.handle && typeof start.handle.setPointerCapture === 'function' && activePointerId !== null) {
        try {
          start.handle.setPointerCapture(activePointerId);
        } catch (_) {}
      }
    }

    if (ghost) {
      ghost.style.left = event.clientX + 14 + 'px';
      ghost.style.top = event.clientY + 14 + 'px';
    }

    // Highlight target column list
    var target = document.elementFromPoint(event.clientX, event.clientY);
    var list = target ? target.closest('.task-column__list') : null;
    if (list !== currentDragOverList) {
      clearDragOverHighlights();
      if (list) {
        list.classList.add('is-drag-over');
        currentDragOverList = list;
      }
    }
  }

  function onPointerUp(event) {
    if (!start) return;

    if (start.handle && typeof start.handle.releasePointerCapture === 'function' && activePointerId !== null) {
      try {
        start.handle.releasePointerCapture(activePointerId);
      } catch (_) {}
    }

    var item = store.getItem(start.card.dataset.itemId);
    if (dragging && item) {
      var target = document.elementFromPoint(event.clientX, event.clientY);
      var list = target ? target.closest('.task-column__list') : null;

      if (!list) {
        var col = target ? target.closest('.task-column') : null;
        if (col) {
          list = col.querySelector('.task-column__list');
        }
      }

      if (list && list.dataset.listFor) {
        var cards = Array.prototype.slice
          .call(list.querySelectorAll('.task-card'))
          .filter(function (card) {
            return card.dataset.itemId !== String(item.item_id);
          });

        var index = cards.findIndex(function (card) {
          var rect = card.getBoundingClientRect();
          return event.clientY < rect.top + rect.height / 2;
        });

        moveBy(item, list.dataset.listFor, index < 0 ? cards.length : index);
      }
    }

    clearDragOverHighlights();
    if (ghost) {
      ghost.remove();
    }
    if (dragging) {
      dragging.classList.remove('is-dragging');
    }

    dragging = null;
    ghost = null;
    start = null;
    activePointerId = null;
  }

  function keyMove(event) {
    if (!event.ctrlKey || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      return;
    }
    var card = event.target.closest('.task-card');
    if (!card) return;
    var item = store.getItem(card.dataset.itemId);
    if (!item) return;

    event.preventDefault();
    var list = ordered(item.board_status);
    var index = list.findIndex(function (candidate) {
      return candidate.item_id === item.item_id;
    });

    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      var order = ['todo', 'doing', 'done'];
      var currentOrderIdx = order.indexOf(item.board_status);
      var targetOrderIdx = Math.max(
        0,
        Math.min(order.length - 1, currentOrderIdx + (event.key === 'ArrowLeft' ? -1 : 1))
      );
      var targetStatus = order[targetOrderIdx];
      moveBy(item, targetStatus, ordered(targetStatus).length);
    } else if (event.key === 'ArrowUp') {
      moveBy(item, item.board_status, Math.max(0, index - 1));
    } else if (event.key === 'ArrowDown') {
      moveBy(item, item.board_status, index + 1);
    }
  }

  function init() {
    var board = document.getElementById('taskBoard');
    if (!board) return;

    board.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('pointermove', onPointerMove);
    document.addEventListener('pointerup', onPointerUp);
    document.addEventListener('pointercancel', onPointerUp);
    board.addEventListener('keydown', keyMove);

    board.addEventListener('click', function (event) {
      var button = event.target.closest('[data-action="menu"]');
      if (button) {
        openMenu(button.closest('.task-card'));
      }
    });

    document.addEventListener('click', function (event) {
      if (!event.target.closest('.task-card__move-menu, [data-action="menu"]')) {
        document.querySelectorAll('.task-card__move-menu').forEach(function (menu) {
          menu.remove();
        });
      }
    });
  }

  modules.dnd = {
    init: init,
    moveBy: moveBy
  };
})(window, document);
