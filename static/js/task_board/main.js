(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var POLL_INTERVAL_MS = 3500;
  var pollTimer = null;
  var isPolling = false;
  var isCreatingQuickAdd = false;

  function isUserInteracting() {
    var dialog = document.getElementById('taskEditorDialog');
    if (dialog && dialog.open) return true;
    if (modules.dnd && modules.dnd.isDragging()) return true;
    if (modules.menu && modules.menu.isOpen()) return true;
    if (modules.select && modules.select.isOpen()) return true;
    var inlineAdd = document.querySelector('.task-inline-add:not([hidden])');
    if (inlineAdd && inlineAdd.contains(document.activeElement)) return true;
    return false;
  }

  async function load(isSilent) {
    if (isPolling) return;
    isPolling = true;

    try {
      var data = await core.request(core.itemsUrl(), { method: 'GET' });
      // Defer syncing while the user is mid-interaction so nothing jumps.
      // 操作中に画面が動かないよう、同期を先送りする。
      if (!isUserInteracting()) {
        store.setAll(data.items, data.categories);
      }
    } catch (err) {
      if (!isSilent) {
        core.toast(err.message || 'タスクの読み込みに失敗しました。', 'error');
      }
    } finally {
      isPolling = false;
    }
  }

  function startPolling() {
    stopPolling();
    pollTimer = window.setInterval(function () {
      if (!document.hidden) {
        load(true);
      }
    }, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function createFromQuickAdd(event) {
    event.preventDefault();
    if (isCreatingQuickAdd) return;
    var input = document.getElementById('taskTitle');
    var prioritySelect = document.getElementById('taskCreatePriority');
    var startDateInput = document.getElementById('taskCreateStartDate');
    var dueDateInput = document.getElementById('taskCreateDueDate');
    var error = document.getElementById('taskCreateError');
    var title = input ? input.value.trim() : '';

    if (error) error.hidden = true;

    if (!title) {
      if (error) {
        error.textContent = 'タスク名を入力してください。';
        error.hidden = false;
      }
      return;
    }
    
    var start_date = startDateInput ? startDateInput.value || null : null;
    var due_date = dueDateInput ? dueDateInput.value || null : null;

    if (start_date && due_date && start_date > due_date) {
      if (error) {
        error.textContent = '開始日は期限日以前の日付を指定してください。';
        error.hidden = false;
      }
      return;
    }

    var button = event.currentTarget.querySelector('button[type="submit"]');
    isCreatingQuickAdd = true;
    if (button) button.disabled = true;

    try {
      await modules.actions.createItem({
        title: title,
        priority: prioritySelect ? prioritySelect.value : 'normal',
        board_status: 'todo',
        start_date: start_date,
        due_date: due_date
      });
      if (input) {
        input.value = '';
        input.focus();
      }
      if (startDateInput) startDateInput.value = '';
      if (dueDateInput) dueDateInput.value = '';
      core.toast('タスクを追加しました。', 'success');
    } catch (err) {
      if (error) {
        error.textContent = err.message || '追加に失敗しました。';
        error.hidden = false;
      }
    } finally {
      isCreatingQuickAdd = false;
      if (button) button.disabled = false;
    }
  }

  function cardsInColumn(card) {
    var list = card.closest('.task-column__list');
    return list ? Array.prototype.slice.call(list.querySelectorAll('.task-card')) : [];
  }

  function focusSibling(card, offset) {
    var cards = cardsInColumn(card);
    var index = cards.indexOf(card);
    var next = cards[index + offset];
    if (next) next.focus();
  }

  function onCardKeydown(event) {
    var card = event.target.closest ? event.target.closest('.task-card') : null;
    if (!card) return;

    var item = store.getItem(card.dataset.itemId);
    if (!item) return;

    var isArrow = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].indexOf(event.key) >= 0;

    if ((event.ctrlKey || event.metaKey) && isArrow) {
      event.preventDefault();
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        var order = core.STATUSES;
        var current = order.indexOf(item.board_status);
        var target = order[
          Math.max(0, Math.min(order.length - 1, current + (event.key === 'ArrowLeft' ? -1 : 1)))
        ];
        if (target !== item.board_status) {
          modules.actions.moveToColumn(item, target);
        }
      } else {
        modules.actions.moveWithin(item, event.key === 'ArrowUp' ? -1 : 1);
      }
      window.setTimeout(function () {
        var moved = document.querySelector('.task-card[data-item-id="' + item.item_id + '"]');
        if (moved) moved.focus();
      }, 60);
      return;
    }

    // Remaining shortcuts only apply when the card itself holds focus.
    // 以降はカード本体にフォーカスがある場合のみ有効。
    if (event.target !== card) return;

    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
      event.preventDefault();
      focusSibling(card, event.key === 'ArrowUp' ? -1 : 1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      modules.editor.open(item);
    } else if (event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault();
      modules.actions.toggleDone(item.item_id);
    } else if (event.key === 'Delete') {
      event.preventDefault();
      modules.actions.deleteItem(item.item_id);
    }
  }

  function initBoardEvents() {
    var board = document.getElementById('taskBoard');
    if (!board) return;

    board.addEventListener('click', function (event) {
      var card = event.target.closest('.task-card');
      if (!card) return;

      if (event.target.closest('[data-action="toggle"]')) {
        modules.actions.toggleDone(card.dataset.itemId);
      } else if (event.target.closest('[data-action="edit"]')) {
        var item = store.getItem(card.dataset.itemId);
        if (item) modules.editor.open(item);
      } else if (event.target.closest('[data-action="menu"]')) {
        modules.actions.openCardMenu(event.target.closest('[data-action="menu"]'), card);
      }
    });

    board.addEventListener('keydown', onCardKeydown);
  }

  function initShortcutHelp() {
    var dialog = document.getElementById('taskShortcutDialog');
    var openButton = document.getElementById('taskShortcutBtn');
    var closeButton = document.getElementById('taskShortcutClose');
    if (!dialog) return;

    function open() {
      if (typeof dialog.showModal === 'function') {
        dialog.showModal();
      } else {
        dialog.setAttribute('open', '');
      }
    }

    if (openButton) openButton.addEventListener('click', open);
    if (closeButton) closeButton.addEventListener('click', function () {
      dialog.close();
    });
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) dialog.close();
    });

    modules.shortcutHelp = { open: open };
  }

  function initGlobalShortcuts() {
    document.addEventListener('keydown', function (event) {
      var tag = (event.target && event.target.tagName) || '';
      var isInput =
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        (event.target && event.target.isContentEditable);

      if (event.key === 'Escape') {
        if (modules.menu && modules.menu.isOpen()) {
          modules.menu.close();
        }
        if (modules.select && modules.select.isOpen()) {
          modules.select.closeAll();
        }
        return;
      }

      if (isInput || event.ctrlKey || event.metaKey || event.altKey) return;

      if (event.key === '/') {
        event.preventDefault();
        var search = document.getElementById('taskSearchInput');
        if (search) search.focus();
      } else if (event.key === 'n' || event.key === 'N') {
        event.preventDefault();
        var titleInput = document.getElementById('taskTitle');
        if (titleInput) titleInput.focus();
      } else if (event.key === 'v' || event.key === 'V') {
        event.preventDefault();
        if (modules.views) modules.views.toggle();
      } else if (event.key === '?') {
        event.preventDefault();
        if (modules.shortcutHelp) modules.shortcutHelp.open();
      }
    });
  }

  function init() {
    if (modules.select) {
      modules.select.init();
    }
    modules.filters.init();
    modules.editor.init();
    modules.columns.init();
    modules.dnd.init();
    modules.calendar.init();
    modules.views.init();
    initBoardEvents();
    initShortcutHelp();
    initGlobalShortcuts();

    var createForm = document.getElementById('taskCreateForm');
    if (createForm) {
      createForm.addEventListener('submit', createFromQuickAdd);
    }

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) {
        load(true);
        startPolling();
      } else {
        stopPolling();
      }
    });

    window.addEventListener('focus', function () {
      load(true);
    });

    load();
    startPolling();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window, document);
