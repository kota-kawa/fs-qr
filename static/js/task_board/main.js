(function (window, document) {
  'use strict';
  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard'); var core = modules.core, store = modules.store;
  function url(suffix) { return '/api/task/' + encodeURIComponent(core.config.roomId) + '/items' + (suffix || ''); }
  async function load() { try { var data = await core.request(url(), { method: 'GET' }); store.setAll(data.items, data.categories); } catch (err) { core.toast(err.message || 'タスクの読み込みに失敗しました。', 'error'); } }
  async function create(event) { event.preventDefault(); var input = document.getElementById('taskTitle'), error = document.getElementById('taskCreateError'), title = input.value.trim(); error.hidden = true; if (!title) { error.textContent = 'タスク名を入力してください。'; error.hidden = false; return; } if (store.getItems().length >= core.config.limits.maxItems) { error.textContent = 'タスク数の上限に達しました。'; error.hidden = false; return; }
    var button = event.currentTarget.querySelector('button[type="submit"]'); button.disabled = true;
    try { var data = await core.request(url(), { method: 'POST', body: JSON.stringify({ title: title, note: '', priority: 'normal', category: '', due_date: null, board_status: 'todo' }) }); store.replace(data.item); input.value = ''; core.toast('タスクを追加しました。', 'success'); }
    catch (err) { error.textContent = err.message || '追加に失敗しました。'; error.hidden = false; } finally { button.disabled = false; }
  }
  async function toggle(card) { var item = store.getItem(card.dataset.itemId); if (!item) { return; } var before = store.snapshot(); var status = item.board_status === 'done' ? 'todo' : 'done'; store.replace(Object.assign({}, item, { board_status: status }));
    try { var data = await core.request(url('/' + item.item_id), { method: 'PATCH', body: JSON.stringify({ version: item.version, board_status: status }) }); store.replace(data.item); modules.render.announce('「' + item.title + '」を' + (status === 'done' ? '完了' : '未着手') + 'にしました'); }
    catch (err) { if (err.status === 409 && err.data && err.data.item) { store.replace(err.data.item); } else { store.restore(before); } core.toast(err.status === 409 ? '他の画面で更新されました。' : (err.message || '更新に失敗しました。'), 'error'); }
  }
  function initColumns() { document.querySelectorAll('.task-column__header').forEach(function (header) { header.addEventListener('click', function () { if (window.matchMedia('(min-width: 900px)').matches) { return; } var column = header.closest('.task-column'); var open = !column.classList.toggle('is-collapsed'); header.setAttribute('aria-expanded', String(open)); }); }); }
  function initCopy() { var button = document.getElementById('taskCopyShare'), input = document.getElementById('taskShareUrl'); if (button && input) { button.addEventListener('click', async function () { try { await navigator.clipboard.writeText(input.value); core.toast('共有URLをコピーしました。', 'success'); } catch (_) { input.select(); document.execCommand('copy'); core.toast('共有URLをコピーしました。', 'success'); } }); } }
  function init() { modules.filters.init(); modules.editor.init(); modules.dnd.init(); initColumns(); initCopy(); document.getElementById('taskCreateForm').addEventListener('submit', create); document.getElementById('taskBoard').addEventListener('click', function (event) { var card = event.target.closest('.task-card'); if (!card) { return; } if (event.target.closest('[data-action="toggle"]')) { toggle(card); } else if (event.target.closest('[data-action="edit"]')) { var item = store.getItem(card.dataset.itemId); if (item) { modules.editor.open(item); } } }); document.addEventListener('visibilitychange', function () { if (!document.hidden) { load(); } }); load(); }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})(window, document);
