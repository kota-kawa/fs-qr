/**
 * Shared accessible custom select (listbox) that progressively enhances a native <select>.
 * retention-select.js と task_board/select.js で重複していたリストボックス実装の共通版。
 *
 * Behaviour is the Task Board superset; the extras are opt-in so the retention
 * select keeps its previous behaviour:
 *   dropUp               … flip the menu upwards when there is no room below
 *   interceptSetters     … re-sync when JS assigns .value / .selectedIndex
 *   observeOptions       … rebuild when <option> children change (MutationObserver)
 *   stopPropagation      … stop key/click events from reaching page-level handlers
 *   alwaysDispatchChange … dispatch 'change' even when the same option is picked again
 *
 * Exposed as window.FSQRCustomSelect and, when app-namespace.js is present,
 * as __FSQR_APP__.api.getShared('customSelect'). CSS class names are supplied by
 * the caller so each wrapper keeps its own stylesheet contract.
 */
(function (window, document) {
  'use strict';

  var activeMenuInstance = null;

  function closeAll() {
    if (activeMenuInstance) {
      activeMenuInstance.close(false);
    }
  }

  function isOpen() {
    return Boolean(activeMenuInstance);
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

  function randomSuffix() {
    return Math.random().toString(36).slice(2, 8);
  }

  /**
   * Enhance one native select.
   * @param {HTMLSelectElement} nativeSelect
   * @param {Object} config
   *   classes: { wrapper, wrapperCompact, wrapperEnhanced, trigger, triggerCompact, triggerLabel, chevron, menu, option, nativeHidden }
   *   compactClass         … native class that switches to the compact variant
   *   wrapper              … existing wrapper element (created when omitted)
   *   insertTriggerBefore  … node inside the wrapper to insert the trigger before (retention arrow)
   *   enhancedFlag         … dataset key used as the "already enhanced" marker
   *   wrapperFlag          … dataset key set on a created wrapper
   *   idPrefix             … fallback id prefix when the select has no id
   *   menuIdFor(selectId), optionIdFor(menuId, index) … id naming hooks
   *   syncHandle           … property name for the sync helper attached to the select
   *   plus the opt-in flags documented above
   */
  function enhance(nativeSelect, config) {
    var cfg = config || {};
    var classes = cfg.classes || {};
    var enhancedFlag = cfg.enhancedFlag || 'customSelectEnhanced';
    if (!nativeSelect || nativeSelect.dataset[enhancedFlag] === 'true') {
      return null;
    }

    var initialOptions = Array.from(nativeSelect.options);
    if (cfg.requireOptions && initialOptions.length === 0) {
      return null;
    }

    var isCompact = Boolean(cfg.compactClass) && nativeSelect.classList.contains(cfg.compactClass);
    var selectId = nativeSelect.id || (cfg.idPrefix || 'customSelect_') + randomSuffix();
    var menuId = typeof cfg.menuIdFor === 'function'
      ? cfg.menuIdFor(selectId)
      : selectId + '-custom-menu';
    var optionIdFor = typeof cfg.optionIdFor === 'function'
      ? cfg.optionIdFor
      : function (baseId, idx) { return baseId + '-opt-' + idx; };

    // Wrapper: reuse the existing one (retention) or create it (task board)
    // ラッパー: 既存要素を使う（retention）か新規生成する（task board）
    var wrapper = cfg.wrapper || null;
    var createdWrapper = false;
    if (!wrapper) {
      wrapper = document.createElement('div');
      wrapper.className = (classes.wrapper || '') + (isCompact && classes.wrapperCompact ? ' ' + classes.wrapperCompact : '');
      if (cfg.wrapperFlag) {
        wrapper.dataset[cfg.wrapperFlag] = 'true';
      }
      createdWrapper = true;
    }
    if (classes.wrapperEnhanced) {
      wrapper.classList.add(classes.wrapperEnhanced);
    }

    // Trigger button / トリガーボタン
    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = (classes.trigger || '') + (isCompact && classes.triggerCompact ? ' ' + classes.triggerCompact : '');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', menuId);
    if (cfg.triggerIdFor !== null) {
      trigger.id = typeof cfg.triggerIdFor === 'function' ? cfg.triggerIdFor(selectId) : selectId + '-trigger';
    }

    var ariaLabel = nativeSelect.getAttribute('aria-label') || nativeSelect.getAttribute('title');
    if (ariaLabel) {
      trigger.setAttribute('aria-label', ariaLabel);
    }

    var labelSpan = null;
    if (classes.triggerLabel) {
      labelSpan = document.createElement('span');
      labelSpan.className = classes.triggerLabel;
      trigger.appendChild(labelSpan);
    }

    if (classes.chevron) {
      var chevronSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      chevronSvg.setAttribute('class', classes.chevron);
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
      trigger.appendChild(chevronSvg);
    }

    function setTriggerLabel(text) {
      if (labelSpan) {
        labelSpan.textContent = text;
      } else {
        trigger.textContent = text;
      }
    }

    // Listbox menu / リストボックス
    var menu = document.createElement('ul');
    menu.id = menuId;
    menu.className = classes.menu || '';
    menu.setAttribute('role', 'listbox');
    menu.tabIndex = -1;

    // Insert into DOM / DOM への組み込み
    if (createdWrapper) {
      nativeSelect.parentNode.insertBefore(wrapper, nativeSelect);
      wrapper.appendChild(nativeSelect);
      wrapper.appendChild(trigger);
    } else {
      var referenceNode = cfg.insertTriggerBefore && cfg.insertTriggerBefore.parentNode === wrapper
        ? cfg.insertTriggerBefore
        : null;
      wrapper.insertBefore(trigger, referenceNode);
    }
    wrapper.appendChild(menu);

    if (classes.nativeHidden) {
      nativeSelect.classList.add(classes.nativeHidden);
    }
    nativeSelect.setAttribute('aria-hidden', 'true');
    nativeSelect.tabIndex = -1;
    nativeSelect.dataset[enhancedFlag] = 'true';

    // Connect any explicit label[for="selectId"] to focus the trigger
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
    var open_ = false;
    var activeIndex = 0;

    function currentOptions() {
      return Array.from(nativeSelect.options);
    }

    function applySelectedAttribute(el, selected) {
      if (selected) {
        el.classList.add('is-selected');
        el.setAttribute('aria-selected', 'true');
      } else {
        el.classList.remove('is-selected');
        if (cfg.removeUnselectedAria) {
          el.removeAttribute('aria-selected');
        } else {
          el.setAttribute('aria-selected', 'false');
        }
      }
    }

    function buildOptions() {
      menu.innerHTML = '';
      optionItems = [];

      var options = currentOptions();
      var currentVal = nativeSelect.value;
      var selectedIdx = nativeSelect.selectedIndex >= 0 ? nativeSelect.selectedIndex : 0;

      if (options.length === 0) {
        setTriggerLabel('');
        return;
      }

      options.forEach(function (opt, idx) {
        var item = document.createElement('li');
        item.className = classes.option || '';
        item.dataset.value = opt.value;
        item.setAttribute('role', 'option');
        item.tabIndex = -1;
        item.id = optionIdFor(menuId, idx);
        item.textContent = opt.textContent;

        if (opt.disabled) {
          item.setAttribute('aria-disabled', 'true');
        }

        var isSel = opt.selected || opt.value === currentVal;
        applySelectedAttribute(item, isSel);
        if (isSel) {
          selectedIdx = idx;
        }

        item.addEventListener('click', function (e) {
          e.preventDefault();
          if (cfg.stopPropagation) {
            e.stopPropagation();
          }
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

      // Never leave a disabled option as the active one / 無効な選択肢をアクティブにしない
      if (options[selectedIdx] && options[selectedIdx].disabled) {
        var firstEnabled = options.findIndex(function (option) { return !option.disabled; });
        selectedIdx = firstEnabled === -1 ? selectedIdx : firstEnabled;
      }

      activeIndex = selectedIdx;
      if (options[activeIndex]) {
        setTriggerLabel(options[activeIndex].textContent);
      }
    }

    function setActive(idx, focusOption) {
      var options = currentOptions();
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
        applySelectedAttribute(el, idx === selIdx);
      });
      var options = currentOptions();
      if (options[selIdx]) {
        setTriggerLabel(options[selIdx].textContent);
      }
    }

    function selectIndex(idx, closeAfter) {
      var options = currentOptions();
      var opt = options[idx];
      if (!opt || opt.disabled) return;

      var changed = nativeSelect.selectedIndex !== idx;
      nativeSelect.selectedIndex = idx;

      updateSelectedUI(idx);
      setActive(idx, false);
      activeIndex = idx;

      if (changed || cfg.alwaysDispatchChange) {
        var event = new Event('change', { bubbles: true });
        nativeSelect.dispatchEvent(event);
      }

      if (closeAfter) {
        close(true);
      }
    }

    function syncFromNative() {
      var options = currentOptions();
      if (options.length !== optionItems.length) {
        buildOptions();
        return;
      }
      var idx = nativeSelect.selectedIndex;
      if (idx >= 0 && options[idx] && !options[idx].disabled) {
        updateSelectedUI(idx);
        setActive(idx, false);
        activeIndex = idx;
      }
    }

    /** Flip the menu upwards when the viewport has no room below. / 下に余白が無ければ上方向へ開く。 */
    function checkPosition() {
      if (!cfg.dropUp) {
        return;
      }
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
      if (open_) return;
      closeAll();

      checkPosition();
      open_ = true;
      wrapper.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');

      var currentIdx = nativeSelect.selectedIndex >= 0 ? nativeSelect.selectedIndex : activeIndex;
      setActive(currentIdx, true);

      document.addEventListener('pointerdown', onOutsideClick, true);
      document.addEventListener('keydown', onGlobalKeydown, true);

      activeMenuInstance = {
        close: close
      };
    }

    function close(focusTrigger) {
      if (!open_) return;
      open_ = false;
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
      if (!open_) return;
      if (e.key === 'Tab') {
        if (!wrapper.contains(e.target)) {
          close(false);
        }
      }
    }

    function consume(e) {
      e.preventDefault();
      if (cfg.stopPropagation) {
        e.stopPropagation();
      }
    }

    function handleTriggerKeydown(e) {
      var options = currentOptions();
      switch (e.key) {
        case 'ArrowDown':
        case 'Down':
          consume(e);
          open();
          setActive(findNextEnabled(options, activeIndex, 1), true);
          break;
        case 'ArrowUp':
        case 'Up':
          consume(e);
          open();
          setActive(findNextEnabled(options, activeIndex, -1), true);
          break;
        case 'Enter':
        case ' ': // Space
          consume(e);
          if (open_) {
            close(false);
          } else {
            open();
          }
          break;
        case 'Escape':
        case 'Esc':
          if (open_) {
            consume(e);
            close(false);
          }
          break;
        default:
          break;
      }
    }

    function handleMenuKeydown(e) {
      var options = currentOptions();
      switch (e.key) {
        case 'ArrowDown':
        case 'Down':
          consume(e);
          setActive(findNextEnabled(options, activeIndex, 1), true);
          break;
        case 'ArrowUp':
        case 'Up':
          consume(e);
          setActive(findNextEnabled(options, activeIndex, -1), true);
          break;
        case 'Home':
          consume(e);
          setActive(findNextEnabled(options, -1, 1), true);
          break;
        case 'End':
          consume(e);
          setActive(findNextEnabled(options, options.length, -1), true);
          break;
        case 'Enter':
        case ' ': // Space
          consume(e);
          selectIndex(activeIndex, true);
          break;
        case 'Escape':
        case 'Esc':
          consume(e);
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
      if (cfg.stopPropagation) {
        e.preventDefault();
        e.stopPropagation();
      }
      if (open_) {
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

    // Intercept .value and .selectedIndex assignments for instant sync (opt-in)
    // JS からの .value / .selectedIndex 代入時にも自動同期する（任意）
    if (cfg.interceptSetters) {
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
    }

    // Observe dynamic option additions/removals (opt-in)
    // 動的な options 変更の監視（任意）
    if (cfg.observeOptions && window.MutationObserver) {
      var observer = new MutationObserver(function () {
        buildOptions();
      });
      observer.observe(nativeSelect, {
        childList: true,
        subtree: true
      });
    }

    buildOptions();

    // Attach sync helper to the native element / 同期ヘルパーを select に添付
    var syncHandle = cfg.syncHandle || '_customSelectSync';
    nativeSelect[syncHandle] = syncFromNative;

    return {
      wrapper: wrapper,
      trigger: trigger,
      menu: menu,
      open: open,
      close: close,
      sync: syncFromNative
    };
  }

  /** Re-sync a select enhanced earlier (no-op otherwise). / 拡張済み select の表示を同期する。 */
  function sync(select, syncHandle) {
    var handle = syncHandle || '_customSelectSync';
    if (select && typeof select[handle] === 'function') {
      select[handle]();
    }
  }

  var customSelect = Object.freeze({
    enhance: enhance,
    closeAll: closeAll,
    isOpen: isOpen,
    sync: sync
  });

  window.FSQRCustomSelect = customSelect;
  var appNamespace = window.__FSQR_APP__;
  if (appNamespace && appNamespace.api) {
    appNamespace.api.setShared('customSelect', customSelect);
  }
})(window, document);
