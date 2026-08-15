(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var query = '';
  var category = '';
  var priority = '';
  var sortBy = 'position';

  var priorityRank = {
    high: 1,
    normal: 2,
    low: 3
  };

  function apply(items) {
    var filtered = items.filter(function (item) {
      // Search keyword
      if (query) {
        var q = query.toLowerCase();
        var matchTitle = item.title && item.title.toLowerCase().indexOf(q) >= 0;
        var matchNote = item.note && item.note.toLowerCase().indexOf(q) >= 0;
        var matchCat = item.category && item.category.toLowerCase().indexOf(q) >= 0;
        if (!matchTitle && !matchNote && !matchCat) {
          return false;
        }
      }
      // Category
      if (category && item.category !== category) {
        return false;
      }
      // Priority
      if (priority && item.priority !== priority) {
        return false;
      }
      return true;
    });

    // Sorting
    return filtered.sort(function (a, b) {
      if (sortBy === 'due_date') {
        if (!a.due_date && !b.due_date) return a.position - b.position || a.item_id - b.item_id;
        if (!a.due_date) return 1;
        if (!b.due_date) return -1;
        if (a.due_date !== b.due_date) return a.due_date.localeCompare(b.due_date);
      } else if (sortBy === 'priority') {
        var rankA = priorityRank[a.priority] || 2;
        var rankB = priorityRank[b.priority] || 2;
        if (rankA !== rankB) return rankA - rankB;
      } else if (sortBy === 'title') {
        var comp = (a.title || '').localeCompare(b.title || '');
        if (comp !== 0) return comp;
      }
      return a.position - b.position || a.item_id - b.item_id;
    });
  }

  function getActiveFilterCount() {
    var count = 0;
    if (query) count++;
    if (category) count++;
    if (priority) count++;
    if (sortBy !== 'position') count++;
    return count;
  }

  function updateFilterUI() {
    var clearBtn = document.getElementById('taskClearFiltersBtn');
    var badge = document.getElementById('taskActiveFilterCount');
    var searchClearBtn = document.getElementById('taskSearchClear');
    var count = getActiveFilterCount();

    if (clearBtn && badge) {
      if (count > 0) {
        clearBtn.hidden = false;
        badge.textContent = String(count);
      } else {
        clearBtn.hidden = true;
      }
    }

    if (searchClearBtn) {
      searchClearBtn.hidden = !query;
    }
  }

  function updateCategories(categories) {
    var select = document.getElementById('taskCategoryFilter');
    if (!select) return;

    var selected = category;
    select.textContent = '';

    var all = document.createElement('option');
    all.value = '';
    all.textContent = 'すべてのカテゴリ';
    select.appendChild(all);

    (categories || []).forEach(function (name) {
      var option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      select.appendChild(option);
    });

    select.value = selected;
  }

  function clearAll() {
    query = '';
    category = '';
    priority = '';
    sortBy = 'position';

    var searchInput = document.getElementById('taskSearchInput');
    var categorySelect = document.getElementById('taskCategoryFilter');
    var prioritySelect = document.getElementById('taskPriorityFilter');
    var sortSelect = document.getElementById('taskSortSelect');

    if (searchInput) searchInput.value = '';
    if (categorySelect) categorySelect.value = '';
    if (prioritySelect) prioritySelect.value = '';
    if (sortSelect) sortSelect.value = 'position';

    updateFilterUI();
    if (modules.render) {
      modules.render.render(modules.store.getItems(), modules.store.getCategories());
    }
  }

  function init() {
    var searchInput = document.getElementById('taskSearchInput');
    var searchClearBtn = document.getElementById('taskSearchClear');
    var categorySelect = document.getElementById('taskCategoryFilter');
    var prioritySelect = document.getElementById('taskPriorityFilter');
    var sortSelect = document.getElementById('taskSortSelect');
    var clearBtn = document.getElementById('taskClearFiltersBtn');

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        query = this.value.trim();
        updateFilterUI();
        modules.render.render(modules.store.getItems(), modules.store.getCategories());
      });
    }

    if (searchClearBtn && searchInput) {
      searchClearBtn.addEventListener('click', function () {
        searchInput.value = '';
        query = '';
        updateFilterUI();
        modules.render.render(modules.store.getItems(), modules.store.getCategories());
        searchInput.focus();
      });
    }

    if (categorySelect) {
      categorySelect.addEventListener('change', function () {
        category = this.value;
        updateFilterUI();
        modules.render.render(modules.store.getItems(), modules.store.getCategories());
      });
    }

    if (prioritySelect) {
      prioritySelect.addEventListener('change', function () {
        priority = this.value;
        updateFilterUI();
        modules.render.render(modules.store.getItems(), modules.store.getCategories());
      });
    }

    if (sortSelect) {
      sortSelect.addEventListener('change', function () {
        sortBy = this.value;
        updateFilterUI();
        modules.render.render(modules.store.getItems(), modules.store.getCategories());
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', clearAll);
    }
  }

  modules.filters = {
    apply: apply,
    updateCategories: updateCategories,
    updateFilterUI: updateFilterUI,
    init: init,
    clearAll: clearAll
  };
})(window, document);
