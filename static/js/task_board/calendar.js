(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;
  var layout = modules.calendarLayout;

  // 週分割・レーン割り当て（連続バーの座標計算）は calendar-layout.js に切り出している。
  // Week splitting and lane packing (bar coordinate math) live in calendar-layout.js.
  var WEEK_LENGTH = layout.WEEK_LENGTH;
  var MAX_LANES = 3; // レーン上限。超過分は「他N件」に集約する / Lane cap; overflow rolls into the "+N more" indicator
  var WEEKDAY_LABELS = ['日', '月', '火', '水', '木', '金', '土'];

  var dateKey = layout.dateKey;
  var parseKey = layout.parseKey;
  var addDays = layout.addDays;

  /**
   * Task identity color palette (N=12).
   * item_id % N でインデックスを決定し、毎回同じタスクに同じ色を割り当てる。
   * Deterministic per-task color: index = item_id % TASK_PALETTE.length
   */
  var TASK_PALETTE = [
    '#2563eb', // blue-600
    '#0891b2', // cyan-600
    '#059669', // emerald-600
    '#65a30d', // lime-600
    '#ca8a04', // yellow-600
    '#ea580c', // orange-600
    '#dc2626', // red-600
    '#9333ea', // purple-600
    '#db2777', // pink-600
    '#0284c7', // sky-600
    '#16a34a', // green-600
    '#d97706'  // amber-600
  ];

  /**
   * Return the deterministic identity color for a task item.
   * タスク固有の識別色を返す（item_id % N でパレットから選択）。
   * @param {Object} item - Task item with item_id
   * @returns {string} CSS color string
   */
  function taskColor(item) {
    var id = Number(item && item.item_id) || 0;
    return TASK_PALETTE[id % TASK_PALETTE.length];
  }

  var state = {
    year: 0,
    month: 0, // 0-11
    selected: ''
  };
  var visibleItems = [];
  var draggingItemId = null;

  function todayKey() {
    return dateKey(new Date());
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

  /** Short date label used inside bar titles/aria-labels, e.g. "8月18日". */
  function shortDateLabel(key) {
    var date = parseKey(key);
    if (!date) return key;
    return date.getMonth() + 1 + '月' + date.getDate() + '日';
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

  function withoutDueDate(items) {
    return items.filter(function (item) {
      return !item.due_date;
    });
  }

  /** Status modifier class shared by both multi-day bars and single-day chips. */
  function itemStateClass(item) {
    if (item.board_status === 'done') return 'is-done';
    if (core.dueDiffDays(item.due_date) < 0) return 'is-overdue';
    if (item.board_status === 'doing') return 'is-doing';
    return '';
  }

  /**
   * Create one bar segment element for a week's `.task-calendar__bars` layer.
   * 週の `.task-calendar__bars` レイヤー用に、期間バー（または単日チップ）の
   * セグメント要素を1つ生成する。開始日〜締切日にまたがる帯は、週境界をまたぐ
   * ときだけ複数のセグメントに分割されて呼び出される（layoutWeekBars 側の仕事）。
   */
  function createBar(segment) {
    var item = segment.item;
    var span = segment.span;

    var bar = document.createElement('button');
    bar.type = 'button';
    bar.draggable = true;
    bar.dataset.calendarOpen = String(item.item_id);
    bar.style.gridColumn = segment.colStart + ' / span ' + segment.colSpan;
    bar.style.gridRow = String(segment.lane + 1);

    // タスク固有色を CSS 変数として設定する（item_id % N でパレットから決定）
    // Set the per-task identity color as a CSS custom property on the bar element
    bar.style.setProperty('--task-item-color', taskColor(item));

    // "task-calendar__bar" is already used by the header toolbar (.task-calendar__bar
    // in the template's <header>), so the period-bar element uses a distinct name.
    // ヘッダーツールバー（テンプレートの <header class="task-calendar__bar">）と
    // クラス名が衝突しないよう、期間バー要素には別名を使う。
    var classes = ['task-calendar__period-bar', itemStateClass(item)];
    if (span.isMultiDay) {
      classes.push('is-multi');
      if (segment.isSegStart) classes.push('is-bar-start');
      if (segment.isSegEnd) classes.push('is-bar-end');
      if (segment.continuesBefore) classes.push('is-continues-before');
      if (segment.continuesAfter) classes.push('is-continues-after');
    } else {
      classes.push('is-single');
    }
    bar.className = classes.filter(Boolean).join(' ');

    var rangeLabel = span.isMultiDay
      ? shortDateLabel(span.startKey) + '〜' + shortDateLabel(span.dueKey)
      : shortDateLabel(span.dueKey);
    bar.title = item.title + '（' + rangeLabel + '）';
    bar.setAttribute('aria-label', item.title + '（' + rangeLabel + '）');

    var text = document.createElement('span');
    text.className = 'task-calendar__period-bar-text';
    text.textContent = item.title;
    bar.appendChild(text);

    return bar;
  }

  /** Build the absolutely-positioned bars overlay for one week row. */
  function createBarsLayer(segments) {
    var layerEl = document.createElement('div');
    layerEl.className = 'task-calendar__bars';
    segments.forEach(function (segment) {
      if (segment.lane >= MAX_LANES) return; // 上限超過分は「他N件」表示に譲る
      layerEl.appendChild(createBar(segment));
    });
    return layerEl;
  }

  function createCell(key, dayItems, overflowCount) {
    var date = parseKey(key);
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

    if (overflowCount > 0) {
      var more = document.createElement('span');
      more.className = 'task-calendar__more';
      more.textContent = '他' + overflowCount + '件';
      cell.appendChild(more);
    }

    return cell;
  }

  /**
   * Build one `.task-calendar__week` row: a background grid of 7 day cells
   * plus a foreground `.task-calendar__bars` overlay carrying the continuous
   * period bars for that week (lanes are shared across all weeks via laneOf).
   *
   * 1週分の `.task-calendar__week` を構築する。背景は7日分のセル、前景は
   * その週の連続バーを乗せる `.task-calendar__bars` オーバーレイ。
   * レーン番号は laneOf を通じて全週で共通なので、同じタスクは常に同じ
   * 縦位置に描画される。
   */
  function createWeek(weekKeys, groups, laneOf) {
    var segments = layout.layoutWeekBars(weekKeys, visibleItems, laneOf);

    var lanesUsed = 0;
    segments.forEach(function (segment) {
      if (segment.lane < MAX_LANES && segment.lane + 1 > lanesUsed) {
        lanesUsed = segment.lane + 1;
      }
    });

    var week = document.createElement('div');
    week.className = 'task-calendar__week';
    week.setAttribute('role', 'row');
    week.style.setProperty('--task-cal-lanes', String(lanesUsed));

    var cellsWrap = document.createElement('div');
    cellsWrap.className = 'task-calendar__week-cells';
    var hasMore = false;
    weekKeys.forEach(function (key) {
      var dayItems = groups[key] || [];
      var overflowCount = dayItems.filter(function (item) {
        var lane = laneOf[String(item.item_id)] || 0;
        return lane >= MAX_LANES;
      }).length;
      if (overflowCount > 0) hasMore = true;
      cellsWrap.appendChild(createCell(key, dayItems, overflowCount));
    });

    // 「他N件」を表示する週だけセルを1行分高くし、バーと文字が重ならないようにする。
    // Weeks that show a "+N more" line reserve one extra text row in the cell
    // height so the bars overlay cannot cover it.
    week.style.setProperty('--task-cal-more', hasMore ? '1' : '0');
    week.appendChild(cellsWrap);
    week.appendChild(createBarsLayer(segments));

    return week;
  }

  function createRow(item) {
    var row = document.createElement('div');
    row.className = 'task-calendar__row';
    row.setAttribute('role', 'listitem');
    row.draggable = true;
    row.dataset.itemId = String(item.item_id);
    row.style.setProperty('--task-item-color', taskColor(item));

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

    var weeks = layout.buildMonthWeeks(state.year, state.month);
    var laneOf = layout.assignLanes(visibleItems);
    weeks.forEach(function (weekKeys) {
      grid.appendChild(createWeek(weekKeys, groups, laneOf));
    });

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

    var groups = layout.groupByDateSpan(visibleItems);
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

  /**
   * Resolve the day cell under a drag event, even when the pointer is over a
   * period bar (which lives in the `.task-calendar__bars` overlay, not
   * inside the cell DOM). Falls back to mapping the pointer's X position onto
   * the week's 7-column grid.
   *
   * ドラッグ位置の下にある日付セルを解決する。ポインタが期間バー
   * （`.task-calendar__bars` オーバーレイ内にあり、セルの子要素ではない）の
   * 上にある場合は、週の7列グリッド上でのX座標から対応する列を割り出す。
   */
  function resolveDropCell(event) {
    var cell = event.target.closest('.task-calendar__cell');
    if (cell) return cell;

    var week = event.target.closest('.task-calendar__week');
    if (!week) return null;
    var cellsWrap = week.querySelector('.task-calendar__week-cells');
    if (!cellsWrap) return null;
    var rect = cellsWrap.getBoundingClientRect();
    if (!rect.width) return null;

    var index = Math.floor(((event.clientX - rect.left) / rect.width) * WEEK_LENGTH);
    index = Math.max(0, Math.min(WEEK_LENGTH - 1, index));
    return cellsWrap.children[index] || null;
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
    var cell = resolveDropCell(event);
    var backlog = event.target.closest('#taskCalendarBacklogList');
    if (!cell && !backlog) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    highlightDropTarget(cell);
  }

  function onDrop(event) {
    if (!draggingItemId) return;
    var cell = resolveDropCell(event);
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
