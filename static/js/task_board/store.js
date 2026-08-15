(function (window) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var items = [];
  var categories = [];
  var listeners = [];
  var lastCalendarDay = '';

  function calendarDay() {
    var now = new Date();
    return [now.getFullYear(), now.getMonth() + 1, now.getDate()].join('-');
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function notify() {
    listeners.forEach(function (listener) {
      try {
        listener(items, categories);
      } catch (err) {
        console.error('Task store listener error:', err);
      }
    });
  }

  function extractCategoriesFromItems(itemList) {
    var set = new Set();
    itemList.forEach(function (it) {
      if (it.category && typeof it.category === 'string' && it.category.trim()) {
        set.add(it.category.trim());
      }
    });
    return Array.from(set).sort();
  }

  /**
   * Compact signature used to skip redundant re-renders while polling.
   * ポーリング時の無駄な再描画を避けるための軽量シグネチャ。
   */
  function signature(list) {
    return list
      .map(function (item) {
        return [
          item.item_id,
          item.version,
          item.board_status,
          item.position,
          item.title,
          item.note,
          item.priority,
          item.category,
          item.due_date
        ].join('');
      })
      .join('');
  }

  function setAll(nextItems, nextCategories) {
    var incoming = Array.isArray(nextItems) ? nextItems : [];
    var today = calendarDay();
    if (
      items.length &&
      signature(incoming) === signature(items) &&
      today === lastCalendarDay
    ) {
      return false;
    }
    items = incoming;
    lastCalendarDay = today;
    if (Array.isArray(nextCategories) && nextCategories.length > 0) {
      categories = nextCategories;
    } else {
      categories = extractCategoriesFromItems(items);
    }
    notify();
    return true;
  }

  function getItems() {
    return items;
  }

  function getCategories() {
    return categories;
  }

  function getItem(id) {
    return items.find(function (item) {
      return Number(item.item_id) === Number(id);
    });
  }

  /** Aggregated board counters used by the progress summary. / 進捗サマリー用の集計。 */
  function getStats() {
    var core = modules.core;
    var stats = {
      total: items.length,
      todo: 0,
      doing: 0,
      done: 0,
      overdue: 0,
      today: 0,
      week: 0
    };

    items.forEach(function (item) {
      if (item.board_status === 'done') {
        stats.done += 1;
        return;
      }
      if (item.board_status === 'doing') {
        stats.doing += 1;
      } else {
        stats.todo += 1;
      }

      var diff = core && core.dueDiffDays ? core.dueDiffDays(item.due_date) : null;
      if (diff === null) return;
      if (diff < 0) {
        stats.overdue += 1;
      } else if (diff === 0) {
        stats.today += 1;
      }
      if (diff >= 0 && diff <= 7) {
        stats.week += 1;
      }
    });

    stats.percent = stats.total > 0 ? Math.round((stats.done / stats.total) * 100) : 0;
    return stats;
  }

  function replace(item) {
    var index = items.findIndex(function (candidate) {
      return Number(candidate.item_id) === Number(item.item_id);
    });
    if (index >= 0) {
      items.splice(index, 1, item);
    } else {
      items.push(item);
    }
    categories = extractCategoriesFromItems(items);
    notify();
  }

  function remove(id) {
    items = items.filter(function (item) {
      return Number(item.item_id) !== Number(id);
    });
    categories = extractCategoriesFromItems(items);
    notify();
  }

  function removeMany(ids) {
    var wanted = new Set(ids.map(Number));
    items = items.filter(function (item) {
      return !wanted.has(Number(item.item_id));
    });
    categories = extractCategoriesFromItems(items);
    notify();
  }

  function snapshot() {
    return clone(items);
  }

  function restore(value) {
    items = Array.isArray(value) ? value : [];
    categories = extractCategoriesFromItems(items);
    notify();
  }

  function subscribe(listener) {
    listeners.push(listener);
    return function () {
      listeners = listeners.filter(function (value) {
        return value !== listener;
      });
    };
  }

  modules.store = {
    setAll: setAll,
    getItems: getItems,
    getCategories: getCategories,
    getItem: getItem,
    getStats: getStats,
    replace: replace,
    remove: remove,
    removeMany: removeMany,
    snapshot: snapshot,
    restore: restore,
    subscribe: subscribe
  };
})(window);
