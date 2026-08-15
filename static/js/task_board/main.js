(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var pollTimer = null;
  var isPolling = false;
  var POLL_INTERVAL_MS = 3500;

  function url(suffix) {
    return '/api/task/' + encodeURIComponent(core.config.roomId) + '/items' + (suffix || '');
  }

  function isUserInteracting() {
    var dialog = document.getElementById('taskEditorDialog');
    if (dialog && dialog.open) return true;
    if (document.querySelector('.is-dragging')) return true;
    return false;
  }

  async function load(isSilent) {
    if (isPolling) return;
    isPolling = true;

    try {
      var data = await core.request(url(), { method: 'GET' });
      // If user is actively dragging or has modal open, defer sync to not disrupt
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

  async function create(event) {
    event.preventDefault();
    var input = document.getElementById('taskTitle');
    var prioritySelect = document.getElementById('taskCreatePriority');
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

    if (store.getItems().length >= core.config.limits.maxItems) {
      if (error) {
        error.textContent = 'タスク数の上限（' + core.config.limits.maxItems + '件）に達しました。';
        error.hidden = false;
      }
      return;
    }

    var button = event.currentTarget.querySelector('button[type="submit"]');
    if (button) button.disabled = true;

    var priority = prioritySelect ? prioritySelect.value : 'normal';

    try {
      var data = await core.request(url(), {
        method: 'POST',
        body: JSON.stringify({
          title: title,
          note: '',
          priority: priority,
          category: '',
          due_date: null,
          board_status: 'todo'
        })
      });
      store.replace(data.item);
      if (input) input.value = '';
      core.toast('タスクを追加しました。', 'success');
    } catch (err) {
      if (error) {
        error.textContent = err.message || '追加に失敗しました。';
        error.hidden = false;
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function toggle(card) {
    var item = store.getItem(card.dataset.itemId);
    if (!item) return;

    var before = store.snapshot();
    var status = item.board_status === 'done' ? 'todo' : 'done';
    store.replace(Object.assign({}, item, { board_status: status }));

    try {
      var data = await core.request(url('/' + item.item_id), {
        method: 'PATCH',
        body: JSON.stringify({ version: item.version, board_status: status })
      });
      store.replace(data.item);
      modules.render.announce(
        '「' + item.title + '」を' + (status === 'done' ? '完了' : '未着手') + 'にしました'
      );
    } catch (err) {
      if (err.status === 409 && err.data && err.data.item) {
        store.replace(err.data.item);
      } else {
        store.restore(before);
      }
      core.toast(
        err.status === 409
          ? '他の画面で更新されました。'
          : (err.message || '更新に失敗しました。'),
        'error'
      );
    }
  }

  function initColumns() {
    document.querySelectorAll('.task-column__header').forEach(function (header) {
      header.addEventListener('click', function () {
        if (window.matchMedia('(min-width: 900px)').matches) return;
        var column = header.closest('.task-column');
        var open = !column.classList.toggle('is-collapsed');
        header.setAttribute('aria-expanded', String(open));
      });
    });

    document.querySelectorAll('.task-column__quick-add').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var status = this.dataset.quickAddFor || 'todo';
        if (modules.editor && modules.editor.openCreate) {
          modules.editor.openCreate(status);
        }
      });
    });
  }

  function initKeyboardShortcuts() {
    document.addEventListener('keydown', function (e) {
      // Don't trigger if typing in an input or textarea
      var tag = (e.target && e.target.tagName) || '';
      var isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      if (e.key === 'Escape') {
        if (modules.editor && modules.editor.close) {
          modules.editor.close();
        }
        return;
      }

      if (!isInput && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.key === '/') {
          e.preventDefault();
          var search = document.getElementById('taskSearchInput');
          if (search) search.focus();
        } else if (e.key === 'n' || e.key === 'N') {
          e.preventDefault();
          var titleInput = document.getElementById('taskTitle');
          if (titleInput) titleInput.focus();
        }
      }
    });
  }

  function init() {
    modules.filters.init();
    modules.editor.init();
    modules.dnd.init();
    initColumns();
    initKeyboardShortcuts();

    var createForm = document.getElementById('taskCreateForm');
    if (createForm) {
      createForm.addEventListener('submit', create);
    }

    var board = document.getElementById('taskBoard');
    if (board) {
      board.addEventListener('click', function (event) {
        var card = event.target.closest('.task-card');
        if (!card) return;

        if (event.target.closest('[data-action="toggle"]')) {
          toggle(card);
        } else if (event.target.closest('[data-action="edit"]')) {
          var item = store.getItem(card.dataset.itemId);
          if (item && modules.editor) {
            modules.editor.open(item);
          }
        }
      });
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
