(function (window, document) {
  'use strict';
  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard'); var core = modules.core, store = modules.store;
  var dragging = null, ghost = null, start = null;
  var labels = { todo: '未着手', doing: '進行中', done: '完了' };
  function ordered(status) { return store.getItems().filter(function (item) { return item.board_status === status; }).sort(function (a, b) { return a.position - b.position || a.item_id - b.item_id; }); }
  function announce(item, status) { modules.render.announce('「' + item.title + '」を' + labels[status] + 'へ移動しました'); }
  async function persist(item, status, position, normalize) {
    var before = store.snapshot(); var changed = Object.assign({}, item, { board_status: status, position: position }); store.replace(changed);
    try {
      var data = await core.request('/api/task/' + encodeURIComponent(core.config.roomId) + '/items/' + item.item_id, { method: 'PATCH', body: JSON.stringify({ version: item.version, board_status: status, position: position }) }); store.replace(data.item);
      if (normalize) { await normalizeColumn(status); if (item.board_status !== status) { await normalizeColumn(item.board_status); } }
      announce(data.item, status);
    } catch (err) { if (err.status === 409 && err.data && err.data.item) { store.replace(err.data.item); } else { store.restore(before); } core.toast(err.status === 409 ? '他の画面で更新されました。' : (err.message || '移動に失敗しました。'), 'error'); }
  }
  async function normalizeColumn(status) { var ids = ordered(status).map(function (item) { return item.item_id; }); var data = await core.request('/api/task/' + encodeURIComponent(core.config.roomId) + '/items/reorder', { method: 'POST', body: JSON.stringify({ board_status: status, ordered_item_ids: ids }) }); data.items.forEach(store.replace); }
  function moveBy(item, targetStatus, targetIndex) {
    var next = ordered(targetStatus).filter(function (candidate) { return candidate.item_id !== item.item_id; }); var index = Math.max(0, Math.min(targetIndex, next.length)); next.splice(index, 0, item);
    var previous = next[index - 1], following = next[index + 1]; var position = previous && following ? Math.floor((previous.position + following.position) / 2) : (previous ? previous.position + 100 : (following ? Math.max(0, following.position - 100) : 100));
    persist(item, targetStatus, position, true);
  }
  function openMenu(card) {
    document.querySelectorAll('.task-card__move-menu').forEach(function (menu) { menu.remove(); }); var item = store.getItem(card.dataset.itemId); if (!item) { return; }
    var menu = document.createElement('div'); menu.className = 'task-card__move-menu'; menu.setAttribute('role', 'menu');
    [['todo', '未着手へ移動'], ['doing', '進行中へ移動'], ['done', '完了へ移動'], ['up', '上へ'], ['down', '下へ']].forEach(function (entry) { var button = document.createElement('button'); button.type = 'button'; button.textContent = entry[1]; button.addEventListener('click', function () { var now = store.getItem(item.item_id); if (!now) { return; } if (entry[0] === 'up' || entry[0] === 'down') { var list = ordered(now.board_status); var index = list.findIndex(function (candidate) { return candidate.item_id === now.item_id; }); moveBy(now, now.board_status, index + (entry[0] === 'up' ? -1 : 2)); } else { moveBy(now, entry[0], ordered(entry[0]).length); } menu.remove(); }); menu.appendChild(button); }); card.appendChild(menu);
  }
  function onPointerDown(event) { var handle = event.target.closest('.task-card__drag-handle'); if (!handle || event.button !== 0) { return; } var card = handle.closest('.task-card'); start = { x: event.clientX, y: event.clientY, card: card }; handle.setPointerCapture && handle.setPointerCapture(event.pointerId); }
  function onPointerMove(event) { if (!start) { return; } if (!dragging && Math.hypot(event.clientX - start.x, event.clientY - start.y) < 8) { return; } if (!dragging) { dragging = start.card; dragging.classList.add('is-dragging'); ghost = dragging.cloneNode(true); ghost.classList.add('task-card--ghost'); document.body.appendChild(ghost); } ghost.style.left = event.clientX + 12 + 'px'; ghost.style.top = event.clientY + 12 + 'px'; }
  function onPointerUp(event) { if (!start) { return; } var item = store.getItem(start.card.dataset.itemId); if (dragging && item) { var target = document.elementFromPoint(event.clientX, event.clientY); var list = target && target.closest('.task-column__list'); if (list) { var cards = Array.prototype.slice.call(list.querySelectorAll('.task-card')).filter(function (card) { return card.dataset.itemId !== String(item.item_id); }); var index = cards.findIndex(function (card) { return event.clientY < card.getBoundingClientRect().top + card.offsetHeight / 2; }); moveBy(item, list.dataset.listFor, index < 0 ? cards.length : index); } } if (ghost) { ghost.remove(); } if (dragging) { dragging.classList.remove('is-dragging'); } dragging = ghost = null; start = null; }
  function keyMove(event) { if (!event.ctrlKey || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) { return; } var card = event.target.closest('.task-card'); if (!card) { return; } var item = store.getItem(card.dataset.itemId); if (!item) { return; } event.preventDefault(); var index = ordered(item.board_status).findIndex(function (candidate) { return candidate.item_id === item.item_id; }); if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { var order = ['todo', 'doing', 'done']; var target = order[Math.max(0, Math.min(order.length - 1, order.indexOf(item.board_status) + (event.key === 'ArrowLeft' ? -1 : 1)))]; moveBy(item, target, ordered(target).length); } else { moveBy(item, item.board_status, index + (event.key === 'ArrowUp' ? -1 : 2)); } }
  function init() { var board = document.getElementById('taskBoard'); if (!board) { return; } board.addEventListener('pointerdown', onPointerDown); document.addEventListener('pointermove', onPointerMove); document.addEventListener('pointerup', onPointerUp); board.addEventListener('keydown', keyMove); board.addEventListener('click', function (event) { var button = event.target.closest('[data-action="menu"]'); if (button) { openMenu(button.closest('.task-card')); } }); document.addEventListener('click', function (event) { if (!event.target.closest('.task-card__move-menu, [data-action="menu"]')) { document.querySelectorAll('.task-card__move-menu').forEach(function (menu) { menu.remove(); }); } }); }
  modules.dnd = { init: init, moveBy: moveBy };
})(window, document);
