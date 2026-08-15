(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;

  var current = null;

  function focusableItems(menu) {
    return Array.prototype.slice.call(menu.querySelectorAll('.task-menu__item:not([disabled])'));
  }

  function close(options) {
    if (!current) return;
    var open = current;
    current = null;

    if (open.anchor) {
      open.anchor.setAttribute('aria-expanded', 'false');
      var card = open.anchor.closest('.task-card');
      if (card) card.classList.remove('is-menu-open');
    }
    if (open.node && open.node.parentNode) {
      open.node.parentNode.removeChild(open.node);
    }
    document.removeEventListener('pointerdown', open.onOutside, true);
    window.removeEventListener('resize', open.onReflow);
    window.removeEventListener('scroll', open.onReflow, true);

    if (!(options && options.silentFocus) && open.anchor && document.contains(open.anchor)) {
      open.anchor.focus();
    }
  }

  /** Place the menu next to its anchor and keep it inside the viewport. */
  /** アンカーの近くに配置しつつ、画面外へはみ出さないように補正する。 */
  function position(node, anchor) {
    var rect = anchor.getBoundingClientRect();
    var size = node.getBoundingClientRect();
    var margin = 8;

    var top = rect.bottom + 6;
    if (top + size.height > window.innerHeight - margin) {
      top = Math.max(margin, rect.top - size.height - 6);
    }

    var left = rect.right - size.width;
    left = Math.min(left, window.innerWidth - size.width - margin);
    left = Math.max(margin, left);

    node.style.top = Math.round(top) + 'px';
    node.style.left = Math.round(left) + 'px';
  }

  function open(anchor, entries) {
    var wasSameAnchor = current && current.anchor === anchor;
    close({ silentFocus: true });
    if (wasSameAnchor) return null;

    var node = document.createElement('div');
    node.className = 'task-menu';
    node.setAttribute('role', 'menu');

    entries.forEach(function (entry) {
      if (!entry) return;
      if (entry.divider) {
        var divider = document.createElement('div');
        divider.className = 'task-menu__divider';
        divider.setAttribute('role', 'separator');
        node.appendChild(divider);
        return;
      }

      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'task-menu__item' + (entry.danger ? ' is-danger' : '');
      button.setAttribute('role', 'menuitem');
      if (entry.disabled) {
        button.disabled = true;
      }

      var glyph = entry.icon && core.icon(entry.icon);
      if (glyph) button.appendChild(glyph);

      var label = document.createElement('span');
      label.textContent = entry.label;
      button.appendChild(label);

      button.addEventListener('click', function () {
        close({ silentFocus: true });
        entry.onSelect();
      });
      node.appendChild(button);
    });

    document.body.appendChild(node);
    position(node, anchor);

    anchor.setAttribute('aria-expanded', 'true');
    var card = anchor.closest('.task-card');
    if (card) card.classList.add('is-menu-open');

    function onOutside(event) {
      if (!node.contains(event.target) && event.target !== anchor && !anchor.contains(event.target)) {
        close({ silentFocus: true });
      }
    }
    // Follow the anchor while the page scrolls; close once it leaves the view.
    // スクロール中はアンカーに追従し、画面外に出たら閉じる。
    function onReflow() {
      var rect = anchor.getBoundingClientRect();
      if (!document.contains(anchor) || rect.bottom < 0 || rect.top > window.innerHeight) {
        close({ silentFocus: true });
        return;
      }
      position(node, anchor);
    }

    node.addEventListener('keydown', function (event) {
      var items = focusableItems(node);
      var index = items.indexOf(document.activeElement);

      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        close();
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        items[(index + 1 + items.length) % items.length].focus();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        items[(index - 1 + items.length) % items.length].focus();
      } else if (event.key === 'Home') {
        event.preventDefault();
        items[0].focus();
      } else if (event.key === 'End') {
        event.preventDefault();
        items[items.length - 1].focus();
      } else if (event.key === 'Tab') {
        close();
      }
    });

    document.addEventListener('pointerdown', onOutside, true);
    window.addEventListener('resize', onReflow);
    window.addEventListener('scroll', onReflow, true);

    current = { node: node, anchor: anchor, onOutside: onOutside, onReflow: onReflow };

    var first = focusableItems(node)[0];
    if (first) first.focus();
    return node;
  }

  modules.menu = {
    open: open,
    close: close,
    isOpen: function () {
      return Boolean(current);
    }
  };
})(window, document);
