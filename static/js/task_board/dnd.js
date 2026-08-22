(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var dragging = false;
  var sortWarned = false;

  function isDragging() {
    return dragging;
  }

  function customOrder() {
    return !modules.filters || modules.filters.isCustomOrder();
  }

  /** Only the drag handle may start a drag, and only while sorted by custom order. */
  /** ドラッグ開始はハンドルからのみ、かつ「カスタム順」のときだけ許可する。 */
  function filterDragStart(event, item) {
    var onHandle = event.target && event.target.closest && event.target.closest('.task-card__drag-handle');
    if (!onHandle) return false;

    if (!customOrder()) {
      if (!sortWarned) {
        sortWarned = true;
        core.toast(
          core.t(
            'task.sort_drag_disabled',
            '並び替え中はドラッグできません。「カスタム順」に戻してください。'
          ),
          'info'
        );
      }
      return true;
    }
    return false;
  }

  function onStart() {
    dragging = true;
  }

  function onEnd(event) {
    dragging = false;

    var item = store.getItem(event.item.dataset.itemId);
    var targetList = event.to;
    var targetStatus = targetList ? targetList.dataset.listFor : null;

    if (item && targetStatus && modules.actions) {
      modules.actions.moveBy(item, targetStatus, event.newDraggableIndex);
    } else if (modules.render) {
      modules.render.render(store.getItems(), store.getTags());
    }
  }

  function init() {
    var board = document.getElementById('taskBoard');
    if (!board || typeof window.Sortable !== 'function') return;

    Array.prototype.forEach.call(board.querySelectorAll('.task-column__list'), function (list) {
      window.Sortable.create(list, {
        group: 'taskBoardColumns',
        draggable: '.task-card',
        handle: '.task-card__drag-handle',
        animation: 150,
        // ネイティブ HTML5 DnD ではなく JS 実装のドラッグを使い、既存の
        // .task-card--ghost（追従カード）/.is-dragging（元位置の半透明表示）
        // の見た目をそのまま流用する。
        // Use the JS-emulated drag (not native HTML5 DnD) so the existing
        // .task-card--ghost (floating clone) / .is-dragging (faded original
        // slot) visuals keep working unchanged.
        forceFallback: true,
        fallbackClass: 'task-card--ghost',
        fallbackOnBody: true,
        ghostClass: 'is-dragging',
        filter: filterDragStart,
        preventOnFilter: false,
        onStart: onStart,
        onEnd: onEnd
      });
    });
  }

  modules.dnd = {
    init: init,
    isDragging: isDragging
  };
})(window, document);
