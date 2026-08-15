(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var store = modules.store;
  var statuses = ['todo', 'doing', 'done'];

  var statusLabels = {
    todo: '未着手',
    doing: '進行中',
    done: '完了'
  };

  function filtered(items) {
    return modules.filters ? modules.filters.apply(items) : items;
  }

  function createCard(item) {
    var card = document.createElement('article');
    card.className = 'task-card';
    card.dataset.itemId = String(item.item_id);
    card.tabIndex = 0;
    card.setAttribute('role', 'listitem');
    card.draggable = false;

    if (item.board_status === 'done') {
      card.classList.add('is-done');
    }

    // Toggle button (checkbox)
    var check = document.createElement('button');
    check.className = 'task-card__check';
    check.type = 'button';
    check.dataset.action = 'toggle';
    check.setAttribute(
      'aria-label',
      item.board_status === 'done' ? '未着手に戻す' : '完了にする'
    );
    check.textContent = item.board_status === 'done' ? '✓' : '';

    // Body
    var body = document.createElement('div');
    body.className = 'task-card__body';

    // Title
    var title = document.createElement('button');
    title.type = 'button';
    title.className = 'task-card__title';
    title.dataset.action = 'edit';
    title.textContent = item.title;
    body.appendChild(title);

    // Note preview
    if (item.note) {
      var note = document.createElement('p');
      note.className = 'task-card__note';
      note.textContent = item.note;
      body.appendChild(note);
    }

    // Meta chips
    var meta = document.createElement('div');
    meta.className = 'task-card__meta';

    // Priority chip
    var priority = document.createElement('span');
    priority.className = 'task-card__chip is-priority-' + (item.priority || 'normal');
    priority.textContent =
      ({ high: '高', normal: '通常', low: '低' })[item.priority] || '通常';
    meta.appendChild(priority);

    // Category chip
    if (item.category) {
      var category = document.createElement('span');
      category.className = 'task-card__category';
      category.textContent = item.category;
      meta.appendChild(category);
    }

    // Due date chip
    if (item.due_date && modules.core && modules.core.formatRelativeDueDate) {
      var dueInfo = modules.core.formatRelativeDueDate(item.due_date);
      if (dueInfo) {
        var due = document.createElement('span');
        due.className = 'task-card__due';
        if (dueInfo.isOverdue && item.board_status !== 'done') {
          due.classList.add('is-overdue');
        } else if (dueInfo.isDueToday && item.board_status !== 'done') {
          due.classList.add('is-due-today');
        }
        due.textContent = dueInfo.text;
        meta.appendChild(due);
      }
    }

    body.appendChild(meta);

    // Drag handle
    var handle = document.createElement('button');
    handle.type = 'button';
    handle.className = 'task-card__drag-handle';
    handle.dataset.action = 'drag';
    handle.setAttribute('aria-label', 'ドラッグして移動');
    handle.setAttribute('title', 'ドラッグして移動');
    handle.textContent = '⠿';

    // Action menu button
    var menu = document.createElement('button');
    menu.type = 'button';
    menu.className = 'task-card__menu-button';
    menu.dataset.action = 'menu';
    menu.setAttribute('aria-label', 'タスクメニュー');
    menu.setAttribute('title', 'メニュー');
    menu.textContent = '⋮';

    card.append(check, body, handle, menu);
    return card;
  }

  function createEmptyState(status) {
    var empty = document.createElement('div');
    empty.className = 'task-column__empty';

    var icon = document.createElement('span');
    icon.className = 'task-column__empty-icon';
    icon.textContent = status === 'done' ? '🎉' : '📋';

    var text = document.createElement('span');
    text.textContent =
      status === 'done'
        ? '完了したタスクはありません'
        : (statusLabels[status] || '') + 'のタスクはありません';

    empty.append(icon, text);
    return empty;
  }

  function render(items, categories) {
    var visible = filtered(items);

    statuses.forEach(function (status) {
      var list = document.querySelector('[data-list-for="' + status + '"]');
      var count = document.querySelector('[data-count-for="' + status + '"]');
      if (!list) return;

      list.textContent = '';
      var columnItems = visible.filter(function (item) {
        return item.board_status === status;
      });

      if (columnItems.length === 0) {
        list.appendChild(createEmptyState(status));
      } else {
        columnItems.forEach(function (item) {
          list.appendChild(createCard(item));
        });
      }

      if (count) {
        count.textContent = String(columnItems.length);
      }
    });

    if (modules.filters) {
      modules.filters.updateCategories(categories);
      modules.filters.updateFilterUI();
    }

    var datalist = document.getElementById('taskCategoryOptions');
    if (datalist) {
      datalist.textContent = '';
      (categories || []).forEach(function (category) {
        var option = document.createElement('option');
        option.value = category;
        datalist.appendChild(option);
      });
    }
  }

  function announce(message) {
    var region = document.getElementById('taskLiveRegion');
    if (region) {
      region.textContent = '';
      window.setTimeout(function () {
        region.textContent = message;
      }, 20);
    }
  }

  modules.render = {
    render: render,
    announce: announce,
    createCard: createCard
  };

  store.subscribe(render);
})(window, document);
