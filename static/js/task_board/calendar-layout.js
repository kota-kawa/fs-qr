(function (window) {
  'use strict';

  // Pure layout calculations for the calendar's period bars (no DOM access).
  // カレンダーの期間バー表示に必要な純粋なレイアウト計算のみを担うモジュール（DOM操作なし）。
  // calendar.js から呼び出され、週分割・レーン割り当てのロジックをここへ切り出している。

  var app = window.__FSQR_APP__;
  if (!app || !app.api) {
    throw new Error('App namespace is not initialized.');
  }

  var modules = app.api.getModuleNamespace('taskBoard');

  var GRID_ROWS = 6;
  var WEEK_LENGTH = 7;

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

  /**
   * Build the 6-week grid of date keys for the given month.
   * 指定した月のグリッド用に6週分（各週7日、日曜始まり）の日付キー配列を作る。
   * @returns {string[][]} 6 arrays of 7 'YYYY-MM-DD' date keys
   */
  function buildMonthWeeks(year, month) {
    var weeks = [];
    var cursor = gridStart(year, month);
    for (var w = 0; w < GRID_ROWS; w += 1) {
      var week = [];
      for (var d = 0; d < WEEK_LENGTH; d += 1) {
        week.push(dateKey(addDays(cursor, w * WEEK_LENGTH + d)));
      }
      weeks.push(week);
    }
    return weeks;
  }

  /**
   * Calculate the date span (start to due) of a task item.
   * タスクの開始日（未設定なら締切日と同じ）から締切日までの期間を算出する。
   * @returns {{startKey: string, dueKey: string, isMultiDay: boolean}|null}
   */
  function getItemSpan(item) {
    if (!item || !item.due_date) return null;
    var dueKey = String(item.due_date);
    var startKey = item.start_date ? String(item.start_date) : dueKey;
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
   * Group items by every date key covered by their span.
   * タスクを開始日〜締切日の全日程キーへ紐付けてグループ化する（日別件数・パネル表示用）。
   * @returns {Object<string, Array>}
   */
  function groupByDateSpan(items) {
    var groups = {};
    if (!Array.isArray(items)) return groups;

    items.forEach(function (item) {
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

  /**
   * Assign a stable lane (0-based row) to every dated task across the whole
   * visible grid, so a task keeps the same vertical position in every week it
   * spans. Tasks whose date ranges never overlap may share a lane.
   *
   * 表示中のタスク全体に対して、終始一貫したレーン番号（0始まり）を割り当てる。
   * 同じタスクは全期間で常に同じレーンに配置され、期間が重ならないタスク同士は
   * 貪欲法（greedy interval packing）でレーンを共有できるため、レーン数を抑えられる。
   *
   * @param {Array} items
   * @returns {Object<string, number>} item_id (string) -> lane index
   */
  function assignLanes(items) {
    var laneOf = {};
    if (!Array.isArray(items)) return laneOf;

    var entries = [];
    items.forEach(function (item) {
      var span = getItemSpan(item);
      if (span) entries.push({ item: item, span: span });
    });

    // 開始日→締切日→item_id の順で安定ソートし、レーン割り当てを決定的にする
    // Sort by start date, then due date, then item_id for a deterministic assignment.
    entries.sort(function (a, b) {
      if (a.span.startKey !== b.span.startKey) {
        return a.span.startKey < b.span.startKey ? -1 : 1;
      }
      if (a.span.dueKey !== b.span.dueKey) {
        return a.span.dueKey < b.span.dueKey ? -1 : 1;
      }
      return (Number(a.item.item_id) || 0) - (Number(b.item.item_id) || 0);
    });

    var laneEnds = []; // laneEnds[i] = そのレーンが現在占有中の最終日（dueKey）
    entries.forEach(function (entry) {
      var laneIndex = -1;
      for (var i = 0; i < laneEnds.length; i += 1) {
        if (laneEnds[i] < entry.span.startKey) {
          laneIndex = i;
          break;
        }
      }
      if (laneIndex === -1) {
        laneIndex = laneEnds.length;
        laneEnds.push(entry.span.dueKey);
      } else {
        laneEnds[laneIndex] = entry.span.dueKey;
      }
      laneOf[String(entry.item.item_id)] = laneIndex;
    });

    return laneOf;
  }

  /**
   * Split every dated task into its bar segment(s) for a single week row.
   * 1週間（7日分の日付キー配列）について、各タスクをその週内のバーのセグメントへ分割する。
   *
   * A segment's column range is clipped to the week. When the clipped edge
   * does not match the task's real start/due date, the segment is flagged as
   * "continuing" on that side so the caller can render a week-boundary cue
   * (flat edge / notch) instead of a rounded cap or arrow head.
   * セグメントの列範囲は週の境界でクリップされる。クリップされた端が実際の
   * 開始日／締切日と一致しない場合は「継続（continuesBefore/After）」として
   * フラグを立て、呼び出し側が週境界の合図（フラット端やノッチ）を描けるようにする。
   *
   * @param {string[]} weekKeys - 7 date keys for the week (Sunday..Saturday)
   * @param {Array} items
   * @param {Object<string, number>} laneOf - result of assignLanes()
   * @returns {Array<Object>} segments: { item, span, colStart, colSpan, lane,
   *   isSegStart, isSegEnd, continuesBefore, continuesAfter }
   */
  function layoutWeekBars(weekKeys, items, laneOf) {
    var segments = [];
    if (!Array.isArray(weekKeys) || weekKeys.length !== WEEK_LENGTH) return segments;

    var weekStart = weekKeys[0];
    var weekEnd = weekKeys[WEEK_LENGTH - 1];

    (items || []).forEach(function (item) {
      var span = getItemSpan(item);
      if (!span) return;
      if (span.dueKey < weekStart || span.startKey > weekEnd) return; // この週に重ならない

      var segStartKey = span.startKey > weekStart ? span.startKey : weekStart;
      var segEndKey = span.dueKey < weekEnd ? span.dueKey : weekEnd;
      var colStart = weekKeys.indexOf(segStartKey) + 1; // CSS grid-column は1始まり
      var colEnd = weekKeys.indexOf(segEndKey) + 1;
      if (colStart < 1 || colEnd < 1) return;

      segments.push({
        item: item,
        span: span,
        colStart: colStart,
        colSpan: colEnd - colStart + 1,
        lane: laneOf ? (laneOf[String(item.item_id)] || 0) : 0,
        isSegStart: segStartKey === span.startKey,
        isSegEnd: segEndKey === span.dueKey,
        continuesBefore: segStartKey !== span.startKey,
        continuesAfter: segEndKey !== span.dueKey
      });
    });

    return segments;
  }

  modules.calendarLayout = {
    GRID_ROWS: GRID_ROWS,
    WEEK_LENGTH: WEEK_LENGTH,
    dateKey: dateKey,
    parseKey: parseKey,
    addDays: addDays,
    gridStart: gridStart,
    buildMonthWeeks: buildMonthWeeks,
    getItemSpan: getItemSpan,
    groupByDateSpan: groupByDateSpan,
    assignLanes: assignLanes,
    layoutWeekBars: layoutWeekBars
  };
})(window);
