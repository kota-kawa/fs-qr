(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;
  var statuses = core.STATUSES;
  var statusLabels = core.STATUS_LABELS;

  var GRIP_PATH =
    'M7 4.5a1.25 1.25 0 11-2.5 0 1.25 1.25 0 012.5 0zm0 5.5a1.25 1.25 0 11-2.5 0 1.25 1.25 0 012.5 0zm0 5.5a1.25 1.25 0 11-2.5 0 1.25 1.25 0 012.5 0zM15.5 4.5a1.25 1.25 0 11-2.5 0 1.25 1.25 0 012.5 0zm0 5.5a1.25 1.25 0 11-2.5 0 1.25 1.25 0 012.5 0zm0 5.5a1.25 1.25 0 11-2.5 0 1.25 1.25 0 012.5 0z';
  var DOTS_PATH =
    'M10 6a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm0 5.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm0 5.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3z';
  var CHECK_PATH =
    'M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z';

  function svgIcon(path, className) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 20 20');
    svg.setAttribute('fill', 'currentColor');
    svg.setAttribute('aria-hidden', 'true');
    if (className) svg.setAttribute('class', className);
    var node = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    node.setAttribute('d', path);
    svg.appendChild(node);
    return svg;
  }

  function filtered(items) {
    return modules.filters ? modules.filters.apply(items) : items;
  }

  function dueInfoFor(item) {
    return item.due_date ? core.formatRelativeDueDate(item.due_date) : null;
  }

  function signatureOf(item) {
    var due = dueInfoFor(item);
    return [
      item.title,
      item.note,
      item.priority,
      item.category,
      item.board_status,
      due ? due.text : '',
      due && due.isOverdue ? 'o' : '',
      due && due.isDueToday ? 't' : ''
    ].join('');
  }

  /** Build the (re-usable) inner content of a card. / カード内部を構築する。 */
  function fillCard(card, item) {
    card.textContent = '';

    var isDone = item.board_status === 'done';
    card.dataset.priority = item.priority || 'normal';
    card.classList.toggle('is-done', isDone);
    card.setAttribute(
      'aria-label',
      item.title + '（' + (statusLabels[item.board_status] || '') + '）'
    );

    var check = document.createElement('button');
    check.type = 'button';
    check.className = 'task-card__check' + (isDone ? ' is-checked' : '');
    check.dataset.action = 'toggle';
    check.setAttribute('aria-pressed', String(isDone));
    check.setAttribute('aria-label', isDone ? '未着手に戻す' : '完了にする');
    check.setAttribute('title', isDone ? '未着手に戻す' : '完了にする');
    if (isDone) {
      check.appendChild(svgIcon(CHECK_PATH, 'task-check-icon'));
    }
    card.appendChild(check);

    var title = document.createElement('button');
    title.type = 'button';
    title.className = 'task-card__title';
    title.dataset.action = 'edit';
    title.textContent = item.title;
    title.setAttribute('title', 'クリックして編集');
    card.appendChild(title);

    var actions = document.createElement('div');
    actions.className = 'task-card__actions';

    var handle = document.createElement('button');
    handle.type = 'button';
    handle.className = 'task-card__action task-card__drag-handle';
    handle.dataset.action = 'drag';
    handle.setAttribute('aria-label', 'ドラッグして移動');
    handle.setAttribute('title', 'ドラッグして移動');
    handle.appendChild(svgIcon(GRIP_PATH));
    actions.appendChild(handle);

    var menu = document.createElement('button');
    menu.type = 'button';
    menu.className = 'task-card__action';
    menu.dataset.action = 'menu';
    menu.setAttribute('aria-label', 'タスク操作メニュー');
    menu.setAttribute('title', 'メニュー');
    menu.setAttribute('aria-haspopup', 'menu');
    menu.setAttribute('aria-expanded', 'false');
    menu.appendChild(svgIcon(DOTS_PATH));
    actions.appendChild(menu);

    card.appendChild(actions);

    if (item.note && item.note.trim()) {
      var note = document.createElement('p');
      note.className = 'task-card__note';
      note.textContent = item.note.trim();
      card.appendChild(note);
    }

    var meta = document.createElement('div');
    meta.className = 'task-card__meta';

    // Priority is shown as the left accent stripe; only non-default values get a chip.
    // 優先度は左端の色帯で示し、通常以外だけチップを表示してノイズを減らす。
    if (item.priority && item.priority !== 'normal') {
      var priority = document.createElement('span');
      priority.className = 'task-card__chip is-priority-' + item.priority;
      priority.textContent = '優先度: ' + (core.PRIORITY_LABELS[item.priority] || item.priority);
      meta.appendChild(priority);
    }

    if (item.category && item.category.trim()) {
      var category = document.createElement('span');
      category.className = 'task-card__category';
      category.textContent = item.category.trim();
      meta.appendChild(category);
    }

    var dueInfo = dueInfoFor(item);
    if (dueInfo) {
      var due = document.createElement('span');
      due.className = 'task-card__due';
      if (dueInfo.isOverdue && !isDone) {
        due.classList.add('is-overdue');
      } else if (dueInfo.isDueToday && !isDone) {
        due.classList.add('is-due-today');
      }
      due.textContent = dueInfo.text;
      meta.appendChild(due);
    }

    card.appendChild(meta);
    card.dataset.signature = signatureOf(item);
    return card;
  }

  function createCard(item) {
    var card = document.createElement('article');
    card.className = 'task-card';
    card.dataset.itemId = String(item.item_id);
    card.tabIndex = 0;
    card.setAttribute('role', 'listitem');
    card.draggable = false;
    return fillCard(card, item);
  }

  function createEmptyState(status) {
    var empty = document.createElement('div');
    empty.className = 'task-column__empty';

    var filtering = modules.filters && modules.filters.hasActiveFilters();

    var icon = document.createElement('span');
    icon.className = 'task-column__empty-icon';
    icon.textContent = filtering ? '🔍' : (status === 'done' ? '🎉' : (status === 'doing' ? '⚡' : '📋'));

    var text = document.createElement('span');
    text.className = 'task-column__empty-text';
    text.textContent = filtering
      ? '条件に一致するタスクはありません'
      : (status === 'done'
          ? '完了したタスクはまだありません'
          : (statusLabels[status] || '') + 'のタスクはありません');

    empty.append(icon, text);

    if (!filtering && status !== 'done') {
      var action = document.createElement('button');
      action.type = 'button';
      action.className = 'task-column__empty-action';
      action.dataset.columnAdd = status;
      action.textContent = '＋ タスクを追加';
      empty.appendChild(action);
    }

    return empty;
  }

  /**
   * Reconcile one column's DOM against the desired item list so that polling
   * does not rebuild (and un-focus) cards that have not actually changed.
   * ポーリングのたびにカードを作り直さないよう、差分だけを DOM に反映する。
   */
  function syncColumn(list, columnItems) {
    var existing = new Map();
    Array.prototype.slice.call(list.querySelectorAll(':scope > .task-card')).forEach(function (card) {
      existing.set(card.dataset.itemId, card);
    });

    list.querySelectorAll(':scope > .task-column__empty').forEach(function (node) {
      node.remove();
    });

    var cursor = list.firstElementChild;
    columnItems.forEach(function (item) {
      var id = String(item.item_id);
      var card = existing.get(id);
      if (card) {
        existing.delete(id);
        if (card.dataset.signature !== signatureOf(item)) {
          fillCard(card, item);
        }
      } else {
        card = createCard(item);
      }

      if (cursor === card) {
        cursor = card.nextElementSibling;
      } else {
        list.insertBefore(card, cursor);
      }
    });

    existing.forEach(function (card) {
      card.remove();
    });
  }

  function updateSummary(stats) {
    var percent = document.getElementById('taskProgressPercent');
    var count = document.getElementById('taskProgressCount');
    var bar = document.getElementById('taskProgressBar');
    var fill = document.getElementById('taskProgressFill');

    if (percent) percent.textContent = stats.percent + '%';
    if (count) count.textContent = stats.done + ' / ' + stats.total + ' 完了';
    // The ring uses pathLength="100", so the offset is simply the remaining %.
    // リングは pathLength="100" なので、残り割合をそのままオフセットにできる。
    if (fill) fill.style.strokeDashoffset = String(100 - stats.percent);
    if (bar) {
      bar.setAttribute('aria-valuenow', String(stats.percent));
      bar.classList.toggle('is-complete', stats.total > 0 && stats.done === stats.total);
    }

    [['overdue', stats.overdue], ['today', stats.today], ['week', stats.week]].forEach(function (pair) {
      var chip = document.querySelector('[data-due-filter="' + pair[0] + '"]');
      if (!chip) return;
      var value = chip.querySelector('[data-stat="' + pair[0] + '"]');
      if (value) value.textContent = String(pair[1]);
      chip.hidden = pair[1] === 0;
    });
  }

  function rememberFocus() {
    var active = document.activeElement;
    if (!active) return null;
    var card = active.closest ? active.closest('.task-card') : null;
    if (!card) return null;
    return {
      itemId: card.dataset.itemId,
      action: active.dataset ? active.dataset.action || '' : '',
      isCard: active === card
    };
  }

  function restoreFocus(memo) {
    if (!memo) return;
    var card = document.querySelector('.task-card[data-item-id="' + memo.itemId + '"]');
    if (!card || card.contains(document.activeElement)) return;
    if (memo.isCard) {
      card.focus();
      return;
    }
    var target = memo.action ? card.querySelector('[data-action="' + memo.action + '"]') : null;
    (target || card).focus();
  }

  function render(items, categories) {
    if (modules.dnd && modules.dnd.isDragging && modules.dnd.isDragging()) {
      // Never reshuffle the DOM mid-drag. / ドラッグ中は DOM を組み替えない。
      return;
    }

    var memo = rememberFocus();
    var visible = filtered(items);
    var filtering = modules.filters && modules.filters.hasActiveFilters();

    statuses.forEach(function (status) {
      var list = document.querySelector('[data-list-for="' + status + '"]');
      var count = document.querySelector('[data-count-for="' + status + '"]');
      var tabCount = document.querySelector('[data-tab-count-for="' + status + '"]');
      if (!list) return;

      var columnItems = visible.filter(function (item) {
        return item.board_status === status;
      });
      var totalItems = items.filter(function (item) {
        return item.board_status === status;
      }).length;

      syncColumn(list, columnItems);
      if (columnItems.length === 0) {
        list.appendChild(createEmptyState(status));
      }

      if (count) {
        count.textContent = filtering
          ? columnItems.length + ' / ' + totalItems
          : String(columnItems.length);
        count.title = filtering ? '絞り込み後の件数 / 全体の件数' : '';
      }
      if (tabCount) {
        tabCount.textContent = String(columnItems.length);
      }
    });

    updateSummary(store.getStats());

    if (modules.filters) {
      modules.filters.updateCategories(categories);
      modules.filters.updateFilterUI();
    }

    var datalist = document.getElementById('taskCategoryOptions');
    if (datalist) {
      var signature = (categories || []).join('');
      if (datalist.dataset.signature !== signature) {
        datalist.dataset.signature = signature;
        datalist.textContent = '';
        (categories || []).forEach(function (category) {
          var option = document.createElement('option');
          option.value = category;
          datalist.appendChild(option);
        });
      }
    }

    restoreFocus(memo);
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
