(function (window) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var items = [];
  var tags = [];
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
        listener(items, tags);
      } catch (err) {
        console.error('Task store listener error:', err);
      }
    });
  }

  /**
   * Tags currently used by the items, as a fallback when the server list is
   * unavailable. 一覧APIのタグが取れないときに、タスク側のタグから復元する。
   */
  function extractTagsFromItems(itemList) {
    var known = new Map();
    itemList.forEach(function (it) {
      (it.tags || []).forEach(function (tag) {
        if (!tag || tag.tag_id === undefined || tag.tag_id === null) return;
        var id = Number(tag.tag_id);
        if (!known.has(id)) {
          known.set(id, { tag_id: id, name: String(tag.name || '') });
        }
      });
    });
    return Array.from(known.values()).sort(function (a, b) {
      return a.name.localeCompare(b.name, 'ja');
    });
  }

  /** Tag ids of one item, as numbers. / タスクに付いたタグIDの一覧。 */
  function tagIdsOf(item) {
    return (item.tags || []).map(function (tag) {
      return Number(tag.tag_id);
    });
  }

  /** Compact tag part of the change signature. / シグネチャ用のタグ表現。 */
  function tagSignature(item) {
    return (item.tags || [])
      .map(function (tag) {
        return String(tag.tag_id) + ':' + String(tag.name);
      })
      .join(',');
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
          tagSignature(item),
          item.due_date
        ].join('');
      })
      .join('');
  }

  function tagListSignature(list) {
    return (list || [])
      .map(function (tag) {
        return String(tag.tag_id) + ':' + String(tag.name);
      })
      .join(',');
  }

  function setAll(nextItems, nextTags) {
    var incoming = Array.isArray(nextItems) ? nextItems : [];
    var today = calendarDay();
    var incomingTags = Array.isArray(nextTags) ? nextTags : null;
    // タグだけが増減した場合も再描画したいので、シグネチャにタグ一覧も含める。
    // The tag list is part of the signature so adding a tag still re-renders.
    if (
      items.length &&
      signature(incoming) === signature(items) &&
      (incomingTags === null || tagListSignature(incomingTags) === tagListSignature(tags)) &&
      today === lastCalendarDay
    ) {
      return false;
    }
    items = incoming;
    lastCalendarDay = today;
    tags = incomingTags !== null ? incomingTags : extractTagsFromItems(items);
    notify();
    return true;
  }

  /** Replace only the room tag list (tag add / rename / delete). */
  function setTags(nextTags) {
    tags = Array.isArray(nextTags) ? nextTags : [];
    notify();
  }

  function getItems() {
    return items;
  }

  function getTags() {
    return tags;
  }

  function getTag(id) {
    return tags.find(function (tag) {
      return Number(tag.tag_id) === Number(id);
    });
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
    notify();
  }

  function remove(id) {
    items = items.filter(function (item) {
      return Number(item.item_id) !== Number(id);
    });
    notify();
  }

  function removeMany(ids) {
    var wanted = new Set(ids.map(Number));
    items = items.filter(function (item) {
      return !wanted.has(Number(item.item_id));
    });
    notify();
  }

  function snapshot() {
    return clone(items);
  }

  function restore(value) {
    items = Array.isArray(value) ? value : [];
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

  /** Remove a deleted tag from every cached item. / 削除したタグを各タスクから外す。 */
  function dropTag(tagId) {
    var wanted = Number(tagId);
    items.forEach(function (item) {
      if (!item.tags) return;
      item.tags = item.tags.filter(function (tag) {
        return Number(tag.tag_id) !== wanted;
      });
    });
    tags = tags.filter(function (tag) {
      return Number(tag.tag_id) !== wanted;
    });
    notify();
  }

  /** Apply a renamed tag to every cached item. / 名前を変えたタグを各タスクへ反映する。 */
  function renameTag(tagId, name) {
    var wanted = Number(tagId);
    items.forEach(function (item) {
      (item.tags || []).forEach(function (tag) {
        if (Number(tag.tag_id) === wanted) tag.name = name;
      });
    });
    tags.forEach(function (tag) {
      if (Number(tag.tag_id) === wanted) tag.name = name;
    });
    notify();
  }

  modules.store = {
    setAll: setAll,
    setTags: setTags,
    getItems: getItems,
    getTags: getTags,
    getTag: getTag,
    tagIdsOf: tagIdsOf,
    dropTag: dropTag,
    renameTag: renameTag,
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
