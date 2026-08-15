(function (window, document) {
  'use strict';
  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core, store = modules.store;
  var dialog, form, error;
  function showError(message) { error.hidden = !message; error.textContent = message || ''; }
  function close() { if (dialog.open) { dialog.close(); } }
  function open(item) {
    dialog = dialog || document.getElementById('taskEditorDialog'); form = form || document.getElementById('taskEditorForm'); error = error || document.getElementById('taskEditorError');
    document.getElementById('taskEditorId').value = item.item_id; document.getElementById('taskEditorVersion').value = item.version;
    document.getElementById('taskEditorTitleInput').value = item.title || ''; document.getElementById('taskEditorNote').value = item.note || '';
    document.getElementById('taskEditorDueDate').value = item.due_date || ''; document.getElementById('taskEditorPriority').value = item.priority || 'normal'; document.getElementById('taskEditorCategory').value = item.category || '';
    showError(''); dialog.showModal(); document.getElementById('taskEditorTitleInput').focus();
  }
  async function save(event) {
    event.preventDefault(); var id = Number(document.getElementById('taskEditorId').value); var current = store.getItem(id); var title = document.getElementById('taskEditorTitleInput').value.trim();
    if (!title) { showError('タスク名を入力してください。'); return; }
    var payload = { version: Number(document.getElementById('taskEditorVersion').value), title: title, note: document.getElementById('taskEditorNote').value.trim(), due_date: document.getElementById('taskEditorDueDate').value || null, priority: document.getElementById('taskEditorPriority').value, category: document.getElementById('taskEditorCategory').value.trim() };
    var before = store.snapshot(); store.replace(Object.assign({}, current, payload));
    try { var data = await core.request('/api/task/' + encodeURIComponent(core.config.roomId) + '/items/' + id, { method: 'PATCH', body: JSON.stringify(payload) }); store.replace(data.item); close(); core.toast('タスクを更新しました。', 'success'); }
    catch (err) { if (err.status === 409 && err.data && err.data.item) { store.replace(err.data.item); core.toast('他の画面で更新されました。最新の内容を表示します。', 'error'); close(); } else { store.restore(before); showError(err.message || '更新に失敗しました。'); } }
  }
  async function remove() {
    var id = Number(document.getElementById('taskEditorId').value); var item = store.getItem(id); if (!item) { return; }
    var ok = window.showConfirmModal ? await window.showConfirmModal('「' + item.title + '」を削除しますか？', { title: 'タスクを削除' }) : false; if (!ok) { return; }
    var before = store.snapshot(); store.remove(id);
    try { await core.request('/api/task/' + encodeURIComponent(core.config.roomId) + '/items/' + id, { method: 'DELETE', body: JSON.stringify({ version: item.version }) }); close(); core.toast('タスクを削除しました。', 'success'); }
    catch (err) { store.restore(before); core.toast(err.message || '削除に失敗しました。', 'error'); }
  }
  function init() {
    dialog = document.getElementById('taskEditorDialog'); form = document.getElementById('taskEditorForm'); error = document.getElementById('taskEditorError'); if (!dialog || !form) { return; }
    form.addEventListener('submit', save); document.getElementById('taskEditorClose').addEventListener('click', close); document.getElementById('taskEditorCancel').addEventListener('click', close); document.getElementById('taskEditorDelete').addEventListener('click', remove);
    dialog.addEventListener('click', function (event) { if (event.target === dialog) { close(); } });
  }
  modules.editor = { init: init, open: open };
})(window, document);
