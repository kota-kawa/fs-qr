(function (window, document) {
  'use strict';
  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard'); var category = ''; var priority = '';
  function apply(items) { return items.filter(function (item) { return (!category || item.category === category) && (!priority || item.priority === priority); }); }
  function updateCategories(categories) { var select = document.getElementById('taskCategoryFilter'); if (!select) { return; } var selected = category; select.textContent = ''; var all = document.createElement('option'); all.value = ''; all.textContent = 'すべて'; select.appendChild(all); categories.forEach(function (name) { var option = document.createElement('option'); option.value = name; option.textContent = name; select.appendChild(option); }); select.value = selected; }
  function init() { var categorySelect = document.getElementById('taskCategoryFilter'); var prioritySelect = document.getElementById('taskPriorityFilter'); if (categorySelect) { categorySelect.addEventListener('change', function () { category = this.value; modules.render.render(modules.store.getItems(), modules.store.getCategories()); }); } if (prioritySelect) { prioritySelect.addEventListener('change', function () { priority = this.value; modules.render.render(modules.store.getItems(), modules.store.getCategories()); }); } }
  modules.filters = { apply: apply, updateCategories: updateCategories, init: init };
})(window, document);
