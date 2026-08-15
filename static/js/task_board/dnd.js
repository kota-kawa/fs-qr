(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;
  var store = modules.store;

  var DRAG_THRESHOLD = 6;
  var EDGE_SIZE = 90;
  var EDGE_SPEED = 16;

  var start = null;
  var dragging = null;
  var ghost = null;
  var placeholder = null;
  var pointerId = null;
  var pointerY = 0;
  var scrollFrame = null;
  var sortWarned = false;

  function isDragging() {
    return Boolean(dragging);
  }

  function customOrder() {
    return !modules.filters || modules.filters.isCustomOrder();
  }

  function ensurePlaceholder() {
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'task-drop-placeholder';
      placeholder.setAttribute('aria-hidden', 'true');
    }
    return placeholder;
  }

  function listUnderPoint(x, y) {
    var target = document.elementFromPoint(x, y);
    if (!target) return null;
    var list = target.closest('.task-column__list');
    if (list) return list;
    var column = target.closest('.task-column');
    return column ? column.querySelector('.task-column__list') : null;
  }

  /** Insert the placeholder at the position matching the pointer. */
  /** ポインタ位置に対応する場所へプレースホルダーを差し込む。 */
  function movePlaceholder(list, clientY) {
    var node = ensurePlaceholder();
    var cards = Array.prototype.slice
      .call(list.querySelectorAll(':scope > .task-card'))
      .filter(function (card) {
        return card !== dragging;
      });

    var reference = null;
    for (var index = 0; index < cards.length; index += 1) {
      var rect = cards[index].getBoundingClientRect();
      if (clientY < rect.top + rect.height / 2) {
        reference = cards[index];
        break;
      }
    }

    if (node.parentNode === list && node.nextElementSibling === reference) {
      return;
    }
    list.insertBefore(node, reference);
  }

  function highlightColumn(list) {
    document.querySelectorAll('.task-column__list.is-drag-over').forEach(function (element) {
      element.classList.remove('is-drag-over');
    });
    document.querySelectorAll('.task-column.is-drop-target').forEach(function (element) {
      element.classList.remove('is-drop-target');
    });
    if (list) {
      list.classList.add('is-drag-over');
      var column = list.closest('.task-column');
      if (column) column.classList.add('is-drop-target');
    }
  }

  function stepAutoScroll() {
    if (!dragging) {
      scrollFrame = null;
      return;
    }
    if (pointerY < EDGE_SIZE) {
      window.scrollBy(0, -EDGE_SPEED);
    } else if (pointerY > window.innerHeight - EDGE_SIZE) {
      window.scrollBy(0, EDGE_SPEED);
    }
    scrollFrame = window.requestAnimationFrame(stepAutoScroll);
  }

  function beginDrag() {
    dragging = start.card;
    pointerY = start.y;

    var rect = dragging.getBoundingClientRect();
    var node = ensurePlaceholder();
    node.style.height = rect.height + 'px';
    dragging.parentNode.insertBefore(node, dragging);

    ghost = dragging.cloneNode(true);
    ghost.classList.add('task-card--ghost');
    ghost.style.width = rect.width + 'px';
    document.body.appendChild(ghost);

    dragging.classList.add('is-dragging');
    dragging.style.display = 'none';
    document.body.style.userSelect = 'none';

    if (start.handle && typeof start.handle.setPointerCapture === 'function' && pointerId !== null) {
      try {
        start.handle.setPointerCapture(pointerId);
      } catch (_) {
        /* pointer capture is best effort / キャプチャ失敗は無視する */
      }
    }

    scrollFrame = window.requestAnimationFrame(stepAutoScroll);
  }

  function cleanup() {
    if (ghost && ghost.parentNode) ghost.parentNode.removeChild(ghost);
    if (placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
    if (dragging) {
      dragging.classList.remove('is-dragging');
      dragging.style.display = '';
    }
    if (scrollFrame) {
      window.cancelAnimationFrame(scrollFrame);
      scrollFrame = null;
    }
    highlightColumn(null);
    document.body.style.userSelect = '';

    ghost = null;
    dragging = null;
    start = null;
    pointerId = null;
  }

  /**
   * Controls that must keep their own click behaviour instead of starting a drag.
   * ドラッグ開始より自身のクリック動作を優先するコントロール。
   */
  function isInteractive(target) {
    return Boolean(
      target.closest(
        'button, a, input, textarea, select, details, summary, .task-menu'
      )
    );
  }

  /** Swallow the click that follows a completed drag. / ドラッグ直後のクリックを無効化。 */
  function swallowNextClick() {
    var timer = null;
    function handler(event) {
      event.stopPropagation();
      event.preventDefault();
      release();
    }
    function release() {
      document.removeEventListener('click', handler, true);
      if (timer) window.clearTimeout(timer);
    }
    document.addEventListener('click', handler, true);
    timer = window.setTimeout(release, 300);
  }

  function onPointerDown(event) {
    if (event.button !== 0 || dragging) return;

    var card = event.target.closest('.task-card');
    if (!card) return;

    var handle = event.target.closest('.task-card__drag-handle');
    // Pointer devices can grab the card body; touch requires the handle so the
    // page keeps scrolling normally.
    // マウスはカード本体、タッチはハンドルのみ。タッチのスクロールを妨げない。
    var grabbable = handle || (event.pointerType === 'mouse' && !isInteractive(event.target));
    if (!grabbable) return;

    if (!customOrder()) {
      if (handle && !sortWarned) {
        sortWarned = true;
        core.toast('並び替え中はドラッグできません。「カスタム順」に戻してください。', 'info');
      }
      return;
    }

    start = { x: event.clientX, y: event.clientY, card: card, handle: handle || card };
    pointerId = event.pointerId;
  }

  function onPointerMove(event) {
    if (!start) return;

    if (!dragging) {
      if (Math.hypot(event.clientX - start.x, event.clientY - start.y) < DRAG_THRESHOLD) {
        return;
      }
      beginDrag();
    }

    event.preventDefault();
    pointerY = event.clientY;

    if (ghost) {
      // Keep the floating copy inside the viewport. / 追従カードを画面内に収める。
      var size = ghost.getBoundingClientRect();
      var left = Math.min(event.clientX + 12, window.innerWidth - size.width - 8);
      var top = Math.min(event.clientY + 12, window.innerHeight - size.height - 8);
      ghost.style.left = Math.max(8, left) + 'px';
      ghost.style.top = Math.max(8, top) + 'px';
    }

    var list = listUnderPoint(event.clientX, event.clientY);
    highlightColumn(list);
    if (list) {
      movePlaceholder(list, event.clientY);
    }
  }

  function onPointerUp() {
    if (!start) return;

    if (start.handle && typeof start.handle.releasePointerCapture === 'function' && pointerId !== null) {
      try {
        start.handle.releasePointerCapture(pointerId);
      } catch (_) {
        /* noop */
      }
    }

    var item = dragging ? store.getItem(dragging.dataset.itemId) : null;
    var targetList = placeholder && placeholder.parentNode ? placeholder.parentNode : null;
    var targetStatus = targetList ? targetList.dataset.listFor : null;
    var targetIndex = 0;

    if (targetList && targetStatus) {
      var siblings = Array.prototype.slice.call(targetList.children);
      var cardsBefore = 0;
      for (var index = 0; index < siblings.length; index += 1) {
        if (siblings[index] === placeholder) break;
        if (siblings[index].classList.contains('task-card') && siblings[index] !== dragging) {
          cardsBefore += 1;
        }
      }
      targetIndex = cardsBefore;
    }

    var wasDragging = Boolean(dragging);
    cleanup();
    if (wasDragging) {
      swallowNextClick();
    }

    if (item && targetStatus && modules.actions) {
      modules.actions.moveBy(item, targetStatus, targetIndex);
    } else if (modules.render) {
      modules.render.render(store.getItems(), store.getCategories());
    }
  }

  function init() {
    var board = document.getElementById('taskBoard');
    if (!board) return;

    board.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('pointermove', onPointerMove, { passive: false });
    document.addEventListener('pointerup', onPointerUp);
    document.addEventListener('pointercancel', onPointerUp);
  }

  modules.dnd = {
    init: init,
    isDragging: isDragging
  };
})(window, document);
