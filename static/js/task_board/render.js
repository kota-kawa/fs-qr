(function (window, document) {
  'use strict';
  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var store = modules.store;
  var statuses = ['todo', 'doing', 'done'];
  function filtered(items) { return modules.filters ? modules.filters.apply(items) : items; }
  function isOverdue(item) { return item.due_date && item.board_status !== 'done' && item.due_date < new Date().toISOString().slice(0, 10); }
  function createCard(item) {
    var card = document.createElement('article'); card.className = 'task-card'; card.dataset.itemId = item.item_id; card.tabIndex = 0; card.setAttribute('role', 'listitem'); card.draggable = false;
    if (item.board_status === 'done') { card.classList.add('is-done'); }
    var check = document.createElement('button'); check.className = 'task-card__check'; check.type = 'button'; check.dataset.action = 'toggle'; check.setAttribute('aria-label', item.board_status === 'done' ? '未完了に戻す' : '完了にする'); check.textContent = item.board_status === 'done' ? '✓' : '';
    var body = document.createElement('div'); body.className = 'task-card__body';
    var title = document.createElement('button'); title.type = 'button'; title.className = 'task-card__title'; title.dataset.action = 'edit'; title.textContent = item.title; body.appendChild(title);
    if (item.note) { var note = document.createElement('p'); note.className = 'task-card__note'; note.textContent = item.note; body.appendChild(note); }
    var meta = document.createElement('div'); meta.className = 'task-card__meta';
    var priority = document.createElement('span'); priority.className = 'task-card__chip is-priority-' + item.priority; priority.textContent = ({ high: '高', normal: '通常', low: '低' })[item.priority] || '通常'; meta.appendChild(priority);
    if (item.category) { var category = document.createElement('span'); category.className = 'task-card__category'; category.textContent = item.category; meta.appendChild(category); }
    if (item.due_date) { var due = document.createElement('span'); due.className = 'task-card__due' + (isOverdue(item) ? ' is-overdue' : ''); due.textContent = '期限 ' + item.due_date; meta.appendChild(due); }
    body.appendChild(meta);
    var handle = document.createElement('button'); handle.type = 'button'; handle.className = 'task-card__drag-handle'; handle.dataset.action = 'drag'; handle.setAttribute('aria-label', 'ドラッグして移動'); handle.textContent = '⠿';
    var menu = document.createElement('button'); menu.type = 'button'; menu.className = 'task-card__menu-button'; menu.dataset.action = 'menu'; menu.setAttribute('aria-label', '移動メニュー'); menu.textContent = '⋮';
    card.append(check, body, handle, menu); return card;
  }
  function render(items, categories) {
    var visible = filtered(items);
    statuses.forEach(function (status) {
      var list = document.querySelector('[data-list-for="' + status + '"]'); var count = document.querySelector('[data-count-for="' + status + '"]'); if (!list) { return; }
      list.textContent = ''; var columnItems = visible.filter(function (item) { return item.board_status === status; }).sort(function (a, b) { return a.position - b.position || a.item_id - b.item_id; });
      columnItems.forEach(function (item) { list.appendChild(createCard(item)); }); if (count) { count.textContent = String(columnItems.length); }
    });
    if (modules.filters) { modules.filters.updateCategories(categories); }
    var datalist = document.getElementById('taskCategoryOptions'); if (datalist) { datalist.textContent = ''; categories.forEach(function (category) { var option = document.createElement('option'); option.value = category; datalist.appendChild(option); }); }
  }
  modules.render = { render: render, announce: function (message) { var region = document.getElementById('taskLiveRegion'); if (region) { region.textContent = ''; window.setTimeout(function () { region.textContent = message; }, 20); } } };
  store.subscribe(render);
})(window, document);
