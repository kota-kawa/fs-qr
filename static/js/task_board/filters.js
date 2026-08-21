(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');

  var state = {
    query: '',
    // 選択したタグのいずれかを持つタスクを表示する（OR 条件）。
    // Items matching ANY of the selected tags are shown (OR semantics).
    tagIds: [],
    priority: '',
    due: '',
    sortBy: 'position'
  };

  var priorityRank = {
    high: 1,
    normal: 2,
    low: 3
  };

  function matchesDue(item) {
    if (!state.due) return true;
    var diff = modules.core.dueDiffDays(item.due_date);
    if (state.due === 'none') return diff === null;
    if (diff === null) return false;
    if (state.due === 'overdue') return diff < 0;
    if (state.due === 'today') return diff === 0;
    if (state.due === 'week') return diff >= 0 && diff <= 7;
    return true;
  }

  function tagNamesOf(item) {
    return (item.tags || []).map(function (tag) {
      return String(tag.name || '');
    });
  }

  function matchesTags(item) {
    if (!state.tagIds.length) return true;
    var ids = (item.tags || []).map(function (tag) {
      return Number(tag.tag_id);
    });
    return state.tagIds.some(function (id) {
      return ids.indexOf(id) >= 0;
    });
  }

  function apply(items) {
    var filtered = items.filter(function (item) {
      if (state.query) {
        var q = state.query.toLowerCase();
        var matchTitle = item.title && item.title.toLowerCase().indexOf(q) >= 0;
        var matchNote = item.note && item.note.toLowerCase().indexOf(q) >= 0;
        var matchTag = tagNamesOf(item).some(function (name) {
          return name.toLowerCase().indexOf(q) >= 0;
        });
        if (!matchTitle && !matchNote && !matchTag) {
          return false;
        }
      }
      if (!matchesTags(item)) {
        return false;
      }
      if (state.priority && item.priority !== state.priority) {
        return false;
      }
      return matchesDue(item);
    });

    return filtered.sort(function (a, b) {
      if (state.sortBy === 'due_date') {
        if (!a.due_date && !b.due_date) return a.position - b.position || a.item_id - b.item_id;
        if (!a.due_date) return 1;
        if (!b.due_date) return -1;
        if (a.due_date !== b.due_date) return a.due_date.localeCompare(b.due_date);
      } else if (state.sortBy === 'priority') {
        var rankA = priorityRank[a.priority] || 2;
        var rankB = priorityRank[b.priority] || 2;
        if (rankA !== rankB) return rankA - rankB;
      } else if (state.sortBy === 'title') {
        var comp = (a.title || '').localeCompare(b.title || '', 'ja');
        if (comp !== 0) return comp;
      }
      return a.position - b.position || a.item_id - b.item_id;
    });
  }

  function isCustomOrder() {
    return state.sortBy === 'position';
  }

  function hasActiveFilters() {
    return Boolean(state.query || state.tagIds.length || state.priority || state.due);
  }

  function getActiveFilterCount() {
    var count = 0;
    if (state.tagIds.length) count++;
    if (state.priority) count++;
    if (state.due) count++;
    if (state.sortBy !== 'position') count++;
    return count;
  }

  function rerender() {
    if (modules.render) {
      modules.render.render(modules.store.getItems(), modules.store.getTags());
    }
  }

  function updateFilterUI() {
    var badge = document.getElementById('taskActiveFilterCount');
    var clearBtn = document.getElementById('taskClearFiltersBtn');
    var searchClearBtn = document.getElementById('taskSearchClear');
    var sortNote = document.getElementById('taskSortNote');
    var count = getActiveFilterCount();

    if (badge) {
      badge.hidden = count === 0;
      badge.textContent = String(count);
    }
    if (clearBtn) {
      clearBtn.hidden = count === 0 && !state.query;
    }
    if (searchClearBtn) {
      searchClearBtn.hidden = !state.query;
    }
    if (sortNote) {
      sortNote.hidden = isCustomOrder();
    }

    document.querySelectorAll('[data-due-filter]').forEach(function (chip) {
      chip.setAttribute('aria-pressed', String(chip.dataset.dueFilter === state.due));
    });
  }

  function toggleTag(tagId) {
    var id = Number(tagId);
    var index = state.tagIds.indexOf(id);
    if (index >= 0) {
      state.tagIds.splice(index, 1);
    } else {
      state.tagIds.push(id);
    }
    updateTags(modules.store.getTags());
    updateFilterUI();
    rerender();
  }

  /** 削除されたタグを絞り込み条件から外す。 / Drop a deleted tag from the filter. */
  function forgetTag(tagId) {
    var index = state.tagIds.indexOf(Number(tagId));
    if (index < 0) return;
    state.tagIds.splice(index, 1);
    updateTags(modules.store.getTags());
    updateFilterUI();
  }

  /**
   * タグ絞り込みのチップ列を描画する。複数選択でき、選んだタグのいずれかを
   * 持つタスクが表示される（OR 条件）。
   * Renders the tag filter chips; selecting several keeps items carrying ANY
   * of them.
   */
  function updateTags(tags) {
    var container = document.getElementById('taskTagFilter');
    if (!container) return;

    var list = tags || [];
    var signature = list
      .map(function (tag) {
        return tag.tag_id + ':' + tag.name;
      })
      .join('');
    var selected = state.tagIds.join(',');
    if (
      container.dataset.signature === signature &&
      container.dataset.selected === selected
    ) {
      return;
    }
    container.dataset.signature = signature;
    container.dataset.selected = selected;
    container.textContent = '';

    if (!list.length) {
      var empty = document.createElement('span');
      empty.className = 'task-tag-filter__empty';
      empty.textContent = 'タグはまだありません';
      container.appendChild(empty);
      return;
    }

    list.forEach(function (tag) {
      var id = Number(tag.tag_id);
      var isOn = state.tagIds.indexOf(id) >= 0;
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'task-tag-chip task-tag-chip--filter' + (isOn ? ' is-selected' : '');
      chip.dataset.tagFilter = String(id);
      chip.setAttribute('aria-pressed', String(isOn));
      chip.textContent = tag.name;
      chip.addEventListener('click', function () {
        toggleTag(id);
      });
      container.appendChild(chip);
    });
  }

  function setDueFilter(value) {
    state.due = state.due === value ? '' : value;
    var select = document.getElementById('taskDueFilter');
    if (select) {
      select.value = state.due;
      if (modules.select) {
        modules.select.sync(select);
      }
    }
    updateFilterUI();
    rerender();
  }

  function clearAll() {
    state.query = '';
    state.tagIds = [];
    state.priority = '';
    state.due = '';
    state.sortBy = 'position';

    var ids = {
      taskSearchInput: '',
      taskPriorityFilter: '',
      taskDueFilter: '',
      taskSortSelect: 'position'
    };
    Object.keys(ids).forEach(function (id) {
      var element = document.getElementById(id);
      if (element) {
        element.value = ids[id];
        if (modules.select) {
          modules.select.sync(element);
        }
      }
    });

    updateTags(modules.store.getTags());
    updateFilterUI();
    rerender();
  }

  function bindSelect(id, key) {
    var select = document.getElementById(id);
    if (!select) return;
    select.addEventListener('change', function () {
      state[key] = this.value;
      updateFilterUI();
      rerender();
    });
  }

  function init() {
    var searchInput = document.getElementById('taskSearchInput');
    var searchClearBtn = document.getElementById('taskSearchClear');
    var clearBtn = document.getElementById('taskClearFiltersBtn');
    var filterToggle = document.getElementById('taskFilterToggle');
    var filterPanel = document.getElementById('taskFilterPanel');

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        state.query = this.value.trim();
        updateFilterUI();
        rerender();
      });
    }

    if (searchClearBtn && searchInput) {
      searchClearBtn.addEventListener('click', function () {
        searchInput.value = '';
        state.query = '';
        updateFilterUI();
        rerender();
        searchInput.focus();
      });
    }

    bindSelect('taskPriorityFilter', 'priority');
    bindSelect('taskDueFilter', 'due');
    bindSelect('taskSortSelect', 'sortBy');

    if (clearBtn) {
      clearBtn.addEventListener('click', clearAll);
    }

    if (filterToggle && filterPanel) {
      filterToggle.addEventListener('click', function () {
        var open = filterPanel.hidden;
        filterPanel.hidden = !open;
        filterToggle.setAttribute('aria-expanded', String(open));
      });
    }

    document.querySelectorAll('[data-due-filter]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        setDueFilter(this.dataset.dueFilter);
        if (filterPanel && filterToggle && filterPanel.hidden && state.due) {
          // Keep the panel in sync so the active condition stays discoverable.
          // 有効な条件が見つけやすいようにパネルを開いておく。
          filterPanel.hidden = false;
          filterToggle.setAttribute('aria-expanded', 'true');
        }
      });
    });
  }

  modules.filters = {
    apply: apply,
    init: init,
    clearAll: clearAll,
    setDueFilter: setDueFilter,
    updateTags: updateTags,
    toggleTag: toggleTag,
    forgetTag: forgetTag,
    updateFilterUI: updateFilterUI,
    isCustomOrder: isCustomOrder,
    hasActiveFilters: hasActiveFilters,
    getState: function () {
      return Object.assign({}, state);
    }
  };
})(window, document);
