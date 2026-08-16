/**
 * Task Board Custom Select Component
 * タスクボード用のモダンカスタムドロップダウンメニューモジュール
 *
 * Provides accessible, beautifully styled custom dropdowns that progressively
 * enhance native <select class="task-select-pill"> elements while maintaining full
 * two-way synchronization, keyboard navigation, and dynamic option updates.
 */
(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');

  var activeMenuInstance = null;

  function closeAll() {
    if (activeMenuInstance) {
      activeMenuInstance.close(false);
    }
  }

  function findNextEnabled(options, fromIndex, step) {
    if (!options || options.length === 0) return fromIndex;
    var len = options.length;
    var idx = fromIndex;
    for (var i = 0; i < len; i++) {
      idx = (idx + step + len) % len;
      if (!options[idx].disabled) {
        return idx;
      }
    }
    return fromIndex;
  }

  function enhanceSelect(nativeSelect) {
    if (!nativeSelect || nativeSelect.dataset.taskSelectEnhanced === 'true') {
      return;
    }

    var isCompact = nativeSelect.classList.contains('task-select-pill--compact');
    var selectId = nativeSelect.id || 'taskSelect_' + Math.random().toString(36).slice(2, 8);
    var menuId = selectId + '-custom-menu';

    // Create wrapper container
    // ラッパー要素の生成
    var wrapper = document.createElement('div');
    wrapper.className = 'task-select-wrapper' + (isCompact ? ' task-select-wrapper--compact' : '');
    wrapper.dataset.taskSelect = 'true';

    // Create trigger button
    // トリガーボタンの生成
    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'task-select-trigger' + (isCompact ? ' task-select-trigger--compact' : '');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', menuId);

    trigger.id = selectId + '-trigger';

    var ariaLabel = nativeSelect.getAttribute('aria-label') || nativeSelect.getAttribute('title');
    if (ariaLabel) {
      trigger.setAttribute('aria-label', ariaLabel);
    }

    var labelSpan = document.createElement('span');
    labelSpan.className = 'task-select-trigger__label';

    var chevronSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chevronSvg.setAttribute('class', 'task-select-trigger__chevron');
    chevronSvg.setAttribute('viewBox', '0 0 20 20');
    chevronSvg.setAttribute('fill', 'currentColor');
    chevronSvg.setAttribute('aria-hidden', 'true');

    var chevronPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    chevronPath.setAttribute('fill-rule', 'evenodd');
    chevronPath.setAttribute(
      'd',
      'M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z'
    );
    chevronPath.setAttribute('clip-rule', 'evenodd');
    chevronSvg.appendChild(chevronPath);

    trigger.appendChild(labelSpan);
    trigger.appendChild(chevronSvg);

    // Create custom menu list
    // カスタムメニューリストの生成
    var menu = document.createElement('ul');
    menu.id = menuId;
    menu.className = 'task-select-menu';
    menu.setAttribute('role', 'listbox');
    menu.tabIndex = -1;

    // Insert wrapper into DOM
    // DOM への組み込み
    nativeSelect.parentNode.insertBefore(wrapper, nativeSelect);
    wrapper.appendChild(nativeSelect);
    wrapper.appendChild(trigger);
    wrapper.appendChild(menu);

    nativeSelect.classList.add('task-select-pill--hidden');
    nativeSelect.setAttribute('aria-hidden', 'true');
    nativeSelect.tabIndex = -1;
    nativeSelect.dataset.taskSelectEnhanced = 'true';

    // Connect any explicit label[for="selectId"] to focus trigger
    // label[for="selectId"] クリック時にトリガーへフォーカス
    if (nativeSelect.id) {
      var labelElem = document.querySelector('label[for="' + nativeSelect.id + '"]');
      if (labelElem) {
        labelElem.addEventListener('click', function (e) {
          if (e.target !== trigger && !trigger.contains(e.target)) {
            trigger.focus();
          }
        });
      }
    }

    var optionItems = [];
    var isOpen = false;
    var activeIndex = 0;

    function buildOptions() {
      menu.innerHTML = '';
      optionItems = [];

      var options = Array.from(nativeSelect.options);
      var currentVal = nativeSelect.value;
      var selectedIdx = nativeSelect.selectedIndex >= 0 ? nativeSelect.selectedIndex : 0;

      if (options.length === 0) {
        labelSpan.textContent = '';
        return;
      }

      options.forEach(function (opt, idx) {
        var item = document.createElement('li');
        item.className = 'task-select-option';
        item.dataset.value = opt.value;
        item.setAttribute('role', 'option');
        item.tabIndex = -1;
        item.id = menuId + '-opt-' + idx;
        item.textContent = opt.textContent;

        if (opt.disabled) {
          item.setAttribute('aria-disabled', 'true');
        }

        var isSel = opt.selected || opt.value === currentVal;
        if (isSel) {
          item.classList.add('is-selected');
          item.setAttribute('aria-selected', 'true');
          selectedIdx = idx;
        } else {
          item.setAttribute('aria-selected', 'false');
        }

        item.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (opt.disabled) return;
          selectIndex(idx, true);
          trigger.focus({ preventScroll: true });
        });

        item.addEventListener('mouseenter', function () {
          setActive(idx, false);
        });

        optionItems.push(item);
        menu.appendChild(item);
      });

      activeIndex = selectedIdx;
      if (options[activeIndex]) {
        labelSpan.textContent = options[activeIndex].textContent;
      }
    }

    function setActive(idx, focusOption) {
      var options = Array.from(nativeSelect.options);
      if (!optionItems[idx] || (options[idx] && options[idx].disabled)) {
        return;
      }

      optionItems.forEach(function (el) {
        el.classList.remove('is-active');
      });

      optionItems[idx].classList.add('is-active');
      menu.setAttribute('aria-activedescendant', optionItems[idx].id);
      activeIndex = idx;

      if (focusOption) {
        optionItems[idx].focus({ preventScroll: true });
        optionItems[idx].scrollIntoView({ block: 'nearest' });
      }
    }

    function updateSelectedUI(selIdx) {
      optionItems.forEach(function (el, idx) {
        if (idx === selIdx) {
          el.classList.add('is-selected');
          el.setAttribute('aria-selected', 'true');
        } else {
          el.classList.remove('is-selected');
          el.setAttribute('aria-selected', 'false');
        }
      });
      var options = Array.from(nativeSelect.options);
      if (options[selIdx]) {
        labelSpan.textContent = options[selIdx].textContent;
      }
    }

    function selectIndex(idx, closeAfter) {
      var options = Array.from(nativeSelect.options);
      var opt = options[idx];
      if (!opt || opt.disabled) return;

      var changed = nativeSelect.selectedIndex !== idx;
      nativeSelect.selectedIndex = idx;

      updateSelectedUI(idx);
      setActive(idx, false);
      activeIndex = idx;

      if (changed) {
        var event = new Event('change', { bubbles: true });
        nativeSelect.dispatchEvent(event);
      }

      if (closeAfter) {
        close(true);
      }
    }

    function syncFromNative() {
      var options = Array.from(nativeSelect.options);
      if (options.length !== optionItems.length) {
        buildOptions();
        return;
      }
      var idx = nativeSelect.selectedIndex;
      if (idx >= 0 && options[idx]) {
        updateSelectedUI(idx);
        activeIndex = idx;
      }
    }

    function checkPosition() {
      var rect = wrapper.getBoundingClientRect();
      var estimatedHeight = Math.min(240, (optionItems.length * 36) + 16);
      var spaceBelow = window.innerHeight - rect.bottom;
      var spaceAbove = rect.top;

      if (spaceBelow < estimatedHeight + 10 && spaceAbove > spaceBelow) {
        wrapper.classList.add('is-dropup');
      } else {
        wrapper.classList.remove('is-dropup');
      }
    }

    function open() {
      if (isOpen) return;
      closeAll();

      checkPosition();
      isOpen = true;
      wrapper.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');

      var currentIdx = nativeSelect.selectedIndex >= 0 ? nativeSelect.selectedIndex : 0;
      setActive(currentIdx, true);

      document.addEventListener('pointerdown', onOutsideClick, true);
      document.addEventListener('keydown', onGlobalKeydown, true);

      activeMenuInstance = {
        close: close
      };
    }

    function close(focusTrigger) {
      if (!isOpen) return;
      isOpen = false;
      wrapper.classList.remove('is-open');
      trigger.setAttribute('aria-expanded', 'false');

      document.removeEventListener('pointerdown', onOutsideClick, true);
      document.removeEventListener('keydown', onGlobalKeydown, true);

      if (activeMenuInstance && activeMenuInstance.close === close) {
        activeMenuInstance = null;
      }

      if (focusTrigger) {
        trigger.focus({ preventScroll: true });
      }
    }

    function onOutsideClick(e) {
      if (!wrapper.contains(e.target)) {
        close(false);
      }
    }

    function onGlobalKeydown(e) {
      if (!isOpen) return;
      if (e.key === 'Tab') {
        if (!wrapper.contains(e.target)) {
          close(false);
        }
      }
    }

    function handleTriggerKeydown(e) {
      var options = Array.from(nativeSelect.options);
      switch (e.key) {
        case 'ArrowDown':
        case 'Down':
          e.preventDefault();
          e.stopPropagation();
          open();
          setActive(findNextEnabled(options, activeIndex, 1), true);
          break;
        case 'ArrowUp':
        case 'Up':
          e.preventDefault();
          e.stopPropagation();
          open();
          setActive(findNextEnabled(options, activeIndex, -1), true);
          break;
        case 'Enter':
        case ' ': // Space
          e.preventDefault();
          e.stopPropagation();
          if (isOpen) {
            close(false);
          } else {
            open();
          }
          break;
        case 'Escape':
        case 'Esc':
          if (isOpen) {
            e.preventDefault();
            e.stopPropagation();
            close(false);
          }
          break;
        default:
          break;
      }
    }

    function handleMenuKeydown(e) {
      var options = Array.from(nativeSelect.options);
      switch (e.key) {
        case 'ArrowDown':
        case 'Down':
          e.preventDefault();
          e.stopPropagation();
          setActive(findNextEnabled(options, activeIndex, 1), true);
          break;
        case 'ArrowUp':
        case 'Up':
          e.preventDefault();
          e.stopPropagation();
          setActive(findNextEnabled(options, activeIndex, -1), true);
          break;
        case 'Home':
          e.preventDefault();
          e.stopPropagation();
          setActive(findNextEnabled(options, -1, 1), true);
          break;
        case 'End':
          e.preventDefault();
          e.stopPropagation();
          setActive(findNextEnabled(options, options.length, -1), true);
          break;
        case 'Enter':
        case ' ': // Space
          e.preventDefault();
          e.stopPropagation();
          selectIndex(activeIndex, true);
          break;
        case 'Escape':
        case 'Esc':
          e.preventDefault();
          e.stopPropagation();
          close(true);
          break;
        case 'Tab':
          close(false);
          break;
        default:
          break;
      }
    }

    trigger.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (isOpen) {
        close(false);
      } else {
        open();
      }
    });

    trigger.addEventListener('keydown', handleTriggerKeydown);
    menu.addEventListener('keydown', handleMenuKeydown);

    nativeSelect.addEventListener('change', function () {
      syncFromNative();
    });

    // Intercept .value and .selectedIndex assignments for instant sync
    // JSからの .value / .selectedIndex 代入時にも自動同期
    var valueDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    if (valueDesc && valueDesc.set) {
      Object.defineProperty(nativeSelect, 'value', {
        get: function () {
          return valueDesc.get.call(this);
        },
        set: function (val) {
          valueDesc.set.call(this, val);
          syncFromNative();
        },
        configurable: true
      });
    }

    var indexDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
    if (indexDesc && indexDesc.set) {
      Object.defineProperty(nativeSelect, 'selectedIndex', {
        get: function () {
          return indexDesc.get.call(this);
        },
        set: function (idx) {
          indexDesc.set.call(this, idx);
          syncFromNative();
        },
        configurable: true
      });
    }

    // Observe dynamic option additions/removals (e.g. #taskCategoryFilter)
    // 動的な options 変更の監視
    if (window.MutationObserver) {
      var observer = new MutationObserver(function () {
        buildOptions();
      });
      observer.observe(nativeSelect, {
        childList: true,
        subtree: true
      });
    }

    // Initial build
    buildOptions();

    // Attach sync helper to native element
    nativeSelect._taskSelectSync = syncFromNative;
  }

  function init() {
    var selects = document.querySelectorAll('select.task-select-pill');
    selects.forEach(function (select) {
      enhanceSelect(select);
    });
  }

  modules.select = {
    init: init,
    enhance: enhanceSelect,
    closeAll: closeAll,
    isOpen: function () {
      return Boolean(activeMenuInstance);
    },
    sync: function (select) {
      if (select && typeof select._taskSelectSync === 'function') {
        select._taskSelectSync();
      }
    }
  };
})(window, document);
