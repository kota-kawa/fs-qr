(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');

  var state = {
    query: '',
    category: '',
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

  function apply(items) {
    var filtered = items.filter(function (item) {
      if (state.query) {
        var q = state.query.toLowerCase();
        var matchTitle = item.title && item.title.toLowerCase().indexOf(q) >= 0;
        var matchNote = item.note && item.note.toLowerCase().indexOf(q) >= 0;
        var matchCat = item.category && item.category.toLowerCase().indexOf(q) >= 0;
        if (!matchTitle && !matchNote && !matchCat) {
          return false;
        }
      }
      if (state.category && item.category !== state.category) {
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
    return Boolean(state.query || state.category || state.priority || state.due);
  }

  function getActiveFilterCount() {
    var count = 0;
    if (state.category) count++;
    if (state.priority) count++;
    if (state.due) count++;
    if (state.sortBy !== 'position') count++;
    return count;
  }

  function rerender() {
    if (modules.render) {
      modules.render.render(modules.store.getItems(), modules.store.getCategories());
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

  function updateCategories(categories) {
    var select = document.getElementById('taskCategoryFilter');
    if (!select) return;

    var names = categories || [];
    var signature = names.join('');
    if (select.dataset.signature === signature) {
      select.value = state.category;
      return;
    }
    select.dataset.signature = signature;
    select.textContent = '';

    var all = document.createElement('option');
    all.value = '';
    all.textContent = 'すべてのカテゴリ';
    select.appendChild(all);

    names.forEach(function (name) {
      var option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      select.appendChild(option);
    });

    select.value = state.category;
    if (modules.select) {
      modules.select.sync(select);
    }
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
    state.category = '';
    state.priority = '';
    state.due = '';
    state.sortBy = 'position';

    var ids = {
      taskSearchInput: '',
      taskCategoryFilter: '',
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

    bindSelect('taskCategoryFilter', 'category');
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
    updateCategories: updateCategories,
    updateFilterUI: updateFilterUI,
    isCustomOrder: isCustomOrder,
    hasActiveFilters: hasActiveFilters,
    getState: function () {
      return Object.assign({}, state);
    }
  };
})(window, document);
