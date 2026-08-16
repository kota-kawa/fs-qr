(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var GRID_ROWS = 6;
  var WEEK_LENGTH = 7;
  var MAX_CHIPS = 3;
  var WEEKDAY_LABELS = ['日', '月', '火', '水', '木', '金', '土'];

  var state = {
    year: 0,
    month: 0, // 0-11
    selected: ''
  };
  var visibleItems = [];
  var draggingItemId = null;

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function dateKey(date) {
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
  }

  function parseKey(key) {
    var parts = String(key || '').split('-');
    if (parts.length !== 3) return null;
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return isNaN(date.getTime()) ? null : date;
  }

  function todayKey() {
    return dateKey(new Date());
  }

  function addDays(date, days) {
    var next = new Date(date.getTime());
    next.setDate(next.getDate() + days);
    return next;
  }

  /** First cell of the month grid (the Sunday on/before the 1st). / グリッド先頭の日曜日。 */
  function gridStart(year, month) {
    var first = new Date(year, month, 1);
    return addDays(first, -first.getDay());
  }

  function monthLabel(year, month) {
    return year + '年' + (month + 1) + '月';
  }

  function dayLabel(key) {
    var date = parseKey(key);
    if (!date) return '-';
    return (
      date.getMonth() + 1 + '月' + date.getDate() + '日（' + WEEKDAY_LABELS[date.getDay()] + '）'
    );
  }

  function element(id) {
    return document.getElementById(id);
  }

  function container() {
    return element('taskCalendar');
  }

  function isActive() {
    var node = container();
    return Boolean(node && !node.hidden);
  }

  /**
   * Calculate the date span (start to due) of a task item.
   * タスクの開始日（作成日）から締切日までの期間を算出する。
   */
  function getItemSpan(item) {
    if (!item || !item.due_date) return null;
    var dueKey = String(item.due_date);
    var startKey = item.created_at ? String(item.created_at).slice(0, 10) : dueKey;
    if (startKey > dueKey) {
      startKey = dueKey;
    }
    return {
      startKey: startKey,
      dueKey: dueKey,
      isMultiDay: startKey < dueKey
    };
  }

  /**
   * Group the visible tasks by all dates included in their span (startKey to dueKey).
   * 表示対象のタスクを開始日〜締切日の全日程セルに紐付けてグループ化する。
   */
  function groupByDateSpan(items) {
    var groups = {};
    if (!Array.isArray(items)) return groups;

    // 期間バーの行位置（スロット）をセル間で安定させるため、開始日・締切日・ID順に安定ソート
    var sorted = items.slice().sort(function (a, b) {
      var spanA = getItemSpan(a);
      var spanB = getItemSpan(b);
      if (!spanA && !spanB) return 0;
      if (!spanA) return 1;
      if (!spanB) return -1;
      if (spanA.startKey !== spanB.startKey) {
        return spanA.startKey < spanB.startKey ? -1 : 1;
      }
      if (spanA.dueKey !== spanB.dueKey) {
        return spanA.dueKey < spanB.dueKey ? -1 : 1;
      }
      return (Number(a.item_id) || 0) - (Number(b.item_id) || 0);
    });

    sorted.forEach(function (item) {
      var span = getItemSpan(item);
      if (!span) return;
      var start = parseKey(span.startKey);
      var due = parseKey(span.dueKey);
      if (!start || !due) return;

      var curr = new Date(start.getTime());
      var safetyCount = 0;
      while (curr <= due && safetyCount < 3660) {
        var key = dateKey(curr);
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
        curr = addDays(curr, 1);
        safetyCount += 1;
      }
    });

    return groups;
  }

  function withoutDueDate(items) {
    return items.filter(function (item) {
      return !item.due_date;
    });
  }

  function chipStateClass(item) {
    if (item.board_status === 'done') return 'is-done';
    if (core.dueDiffDays(item.due_date) < 0) return 'is-overdue';
    if (item.board_status === 'doing') return 'is-doing';
    return '';
  }

  /**
   * Create a chip or span bar element for the calendar cell.
   * カレンダーセル用のタスクチップまたは期間バーを生成する（タスク名は締切日のみ表示）。
   */
  function createChip(item, currentKey) {
    var span = getItemSpan(item);
    var isMultiDay = Boolean(span && span.isMultiDay);
    var isDue = !span || currentKey === span.dueKey;
    var isStart = Boolean(span && currentKey === span.startKey);

    var chip = document.createElement('button');
    chip.type = 'button';
    chip.draggable = true;
    chip.dataset.calendarOpen = String(item.item_id);

    var stateClass = chipStateClass(item);
    var spanClass = '';

    if (isMultiDay) {
      if (isDue) {
        spanClass = 'is-span-end';
      } else if (isStart) {
        spanClass = 'is-span-bar is-span-start';
      } else {
        spanClass = 'is-span-bar is-span-mid';
      }
    } else {
      spanClass = 'is-single';
    }

    chip.className = ['task-calendar__chip', 'task-cal-chip', stateClass, spanClass]
      .filter(Boolean)
      .join(' ');

    if (isDue) {
      // 締切日または単日タスク：タスク名を表示
      chip.title = isMultiDay ? item.title + ' (締切日)' : item.title;
      chip.setAttribute('aria-label', item.title + (isMultiDay ? '（締切日）' : ''));

      var text = document.createElement('span');
      text.className = 'task-calendar__chip-text task-cal-chip-text';
      text.textContent = item.title;
      chip.appendChild(text);
    } else {
      // 開始日〜締切日前日：タスク名は表示せず色付きバーのみ
      chip.title = item.title + ' (期間: ' + span.startKey + ' 〜 ' + span.dueKey + ')';
      chip.setAttribute('aria-label', item.title + '（期間中）');
    }

    return chip;
  }

  function createCell(date, dayItems) {
    var key = dateKey(date);
    var cell = document.createElement('div');
    cell.className = 'task-calendar__cell';
    cell.dataset.date = key;
    cell.setAttribute('role', 'gridcell');
    cell.tabIndex = key === state.selected ? 0 : -1;
    cell.setAttribute('aria-selected', String(key === state.selected));
    cell.setAttribute(
      'aria-label',
      dayLabel(key) + ' タスク' + dayItems.length + '件'
    );

    if (date.getMonth() !== state.month) cell.classList.add('is-outside');
    if (key === todayKey()) cell.classList.add('is-today');
    if (key === state.selected) cell.classList.add('is-selected');
    if (date.getDay() === 0) cell.classList.add('is-sunday');
    if (date.getDay() === 6) cell.classList.add('is-saturday');

    var head = document.createElement('div');
    head.className = 'task-calendar__cell-head';

    var number = document.createElement('span');
    number.className = 'task-calendar__date';
    number.textContent = String(date.getDate());
    head.appendChild(number);

    if (dayItems.length > 0) {
      var overdue = dayItems.some(function (item) {
        return item.board_status !== 'done' && core.dueDiffDays(item.due_date) < 0;
      });
      var count = document.createElement('span');
      count.className = 'task-calendar__cell-count' + (overdue ? ' is-overdue' : '');
      count.textContent = String(dayItems.length);
      head.appendChild(count);
    }
    cell.appendChild(head);

    var chips = document.createElement('div');
    chips.className = 'task-calendar__chips';
    dayItems.slice(0, MAX_CHIPS).forEach(function (item) {
      chips.appendChild(createChip(item, key));
    });
    cell.appendChild(chips);

    if (dayItems.length > MAX_CHIPS) {
      var more = document.createElement('span');
      more.className = 'task-calendar__more';
      more.textContent = '他' + (dayItems.length - MAX_CHIPS) + '件';
      cell.appendChild(more);
    }

    return cell;
  }

  function createRow(item) {
    var row = document.createElement('div');
    row.className = 'task-calendar__row';
    row.setAttribute('role', 'listitem');
    row.draggable = true;
    row.dataset.itemId = String(item.item_id);

    var isDone = item.board_status === 'done';
    if (isDone) row.classList.add('is-done');

    var check = document.createElement('button');
    check.type = 'button';
    check.className = 'task-card__check' + (isDone ? ' is-checked' : '');
    check.dataset.calendarToggle = String(item.item_id);
    check.setAttribute('aria-pressed', String(isDone));
    check.setAttribute('aria-label', isDone ? '未着手に戻す' : '完了にする');
    if (isDone) {
      var icon = core.icon('check');
      if (icon) {
        icon.setAttribute('class', 'task-check-icon');
        check.appendChild(icon);
      }
    }
    row.appendChild(check);

    var title = document.createElement('button');
    title.type = 'button';
    title.className = 'task-calendar__row-title';
    title.dataset.calendarOpen = String(item.item_id);
    title.textContent = item.title;
    title.title = 'クリックして編集';
    row.appendChild(title);

    var status = document.createElement('span');
    status.className = 'task-calendar__row-status is-' + item.board_status;
    status.textContent = core.STATUS_LABELS[item.board_status] || item.board_status;
    row.appendChild(status);

    return row;
  }

  function fillList(list, items, emptyText) {
    if (!list) return;
    list.textContent = '';
    if (items.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'task-calendar__empty';
      empty.textContent = emptyText;
      list.appendChild(empty);
      return;
    }
    items.forEach(function (item) {
      list.appendChild(createRow(item));
    });
  }

  function renderGrid(groups) {
    var grid = element('taskCalendarGrid');
    var label = element('taskCalendarLabel');
    if (!grid) return;

    if (label) label.textContent = monthLabel(state.year, state.month);

    var hadFocus = grid.contains(document.activeElement);
    grid.textContent = '';

    var cursor = gridStart(state.year, state.month);
    for (var index = 0; index < GRID_ROWS * WEEK_LENGTH; index += 1) {
      var date = addDays(cursor, index);
      grid.appendChild(createCell(date, groups[dateKey(date)] || []));
    }

    // Keep keyboard focus inside the grid after a rebuild.
    // 再描画のあともキーボード操作の位置を保つ。
    if (hadFocus) {
      var selected = grid.querySelector('.task-calendar__cell.is-selected');
      if (selected) selected.focus();
    }
  }

  function renderPanels(groups) {
    var dayLabelNode = element('taskCalendarDayLabel');
    if (dayLabelNode) dayLabelNode.textContent = dayLabel(state.selected);

    fillList(
      element('taskCalendarDayList'),
      groups[state.selected] || [],
      'この日のタスクはありません'
    );

    var backlog = withoutDueDate(visibleItems);
    var backlogCount = element('taskCalendarBacklogCount');
    if (backlogCount) backlogCount.textContent = String(backlog.length);
    fillList(
      element('taskCalendarBacklogList'),
      backlog,
      '期限が未設定のタスクはありません'
    );
  }

  /** Redraw the calendar with the currently visible (filtered) tasks. */
  /** 絞り込み後のタスクでカレンダーを描き直す。 */
  function render(items) {
    visibleItems = Array.isArray(items) ? items : [];
    if (!isActive()) return;

    var groups = groupByDateSpan(visibleItems);
    renderGrid(groups);
    renderPanels(groups);
  }

  function refresh() {
    var items = store.getItems();
    render(modules.filters ? modules.filters.apply(items) : items);
  }

  function showMonthOf(key) {
    var date = parseKey(key);
    if (!date) return;
    state.year = date.getFullYear();
    state.month = date.getMonth();
  }

  function select(key, options) {
    if (!parseKey(key)) return;
    state.selected = key;
    showMonthOf(key);
    refresh();

    if (options && options.focusCell) {
      var cell = document.querySelector('.task-calendar__cell.is-selected');
      if (cell) cell.focus();
    }
  }

  function shiftMonth(offset) {
    var next = new Date(state.year, state.month + offset, 1);
    state.year = next.getFullYear();
    state.month = next.getMonth();
    refresh();
  }

  function openItem(itemId) {
    var item = store.getItem(itemId);
    if (item && modules.editor) modules.editor.open(item);
  }

  function addForSelectedDay() {
    if (modules.editor) {
      modules.editor.openCreate('todo', { dueDate: state.selected });
    }
  }

  function onClick(event) {
    var toggle = event.target.closest('[data-calendar-toggle]');
    if (toggle) {
      modules.actions.toggleDone(toggle.dataset.calendarToggle);
      return;
    }

    var opener = event.target.closest('[data-calendar-open]');
    if (opener) {
      openItem(opener.dataset.calendarOpen);
      return;
    }

    var cell = event.target.closest('.task-calendar__cell');
    if (cell) {
      select(cell.dataset.date);
    }
  }

  function onGridKeydown(event) {
    var cell = event.target.closest ? event.target.closest('.task-calendar__cell') : null;
    if (!cell) return;

    var offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -WEEK_LENGTH, ArrowDown: WEEK_LENGTH };
    if (Object.prototype.hasOwnProperty.call(offsets, event.key)) {
      var current = parseKey(cell.dataset.date);
      if (!current) return;
      event.preventDefault();
      select(dateKey(addDays(current, offsets[event.key])), { focusCell: true });
      return;
    }

    if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault();
      select(cell.dataset.date);
      addForSelectedDay();
    }
  }

  function highlightDropTarget(cell) {
    document.querySelectorAll('.task-calendar__cell.is-drop-target').forEach(function (node) {
      if (node !== cell) node.classList.remove('is-drop-target');
    });
    if (cell) cell.classList.add('is-drop-target');
  }

  function onDragStart(event) {
    var source = event.target.closest('[data-calendar-open], .task-calendar__row');
    if (!source) return;
    draggingItemId = source.dataset.calendarOpen || source.dataset.itemId || null;
    if (!draggingItemId) return;
    source.classList.add('is-dragging');
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move';
      // Firefox requires payload data for the drag to start.
      // Firefox ではデータを設定しないとドラッグが始まらない。
      event.dataTransfer.setData('text/plain', draggingItemId);
    }
  }

  function onDragEnd() {
    draggingItemId = null;
    highlightDropTarget(null);
    document.querySelectorAll('.is-dragging').forEach(function (node) {
      node.classList.remove('is-dragging');
    });
  }

  function onDragOver(event) {
    if (!draggingItemId) return;
    var cell = event.target.closest('.task-calendar__cell');
    var backlog = event.target.closest('#taskCalendarBacklogList');
    if (!cell && !backlog) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    highlightDropTarget(cell);
  }

  function onDrop(event) {
    if (!draggingItemId) return;
    var cell = event.target.closest('.task-calendar__cell');
    var backlog = event.target.closest('#taskCalendarBacklogList');
    if (!cell && !backlog) return;

    event.preventDefault();
    var itemId = draggingItemId;
    onDragEnd();
    modules.actions.setDueDate(itemId, cell ? cell.dataset.date : null);
  }

  function init() {
    var node = container();
    if (!node) return;

    state.selected = todayKey();
    showMonthOf(state.selected);

    node.addEventListener('click', onClick);
    node.addEventListener('dragstart', onDragStart);
    node.addEventListener('dragend', onDragEnd);
    node.addEventListener('dragover', onDragOver);
    node.addEventListener('drop', onDrop);

    var grid = element('taskCalendarGrid');
    if (grid) grid.addEventListener('keydown', onGridKeydown);

    node.querySelectorAll('[data-calendar-nav]').forEach(function (button) {
      button.addEventListener('click', function () {
        shiftMonth(Number(button.dataset.calendarNav) || 0);
      });
    });

    var today = element('taskCalendarToday');
    if (today) {
      today.addEventListener('click', function () {
        select(todayKey());
      });
    }

    var add = element('taskCalendarAdd');
    if (add) add.addEventListener('click', addForSelectedDay);
  }

  modules.calendar = {
    init: init,
    render: render,
    refresh: refresh,
    select: select,
    getSelectedDate: function () {
      return state.selected;
    }
  };
})(window, document);
