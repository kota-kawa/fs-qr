/** Task Board adapter for the shared custom select. */
(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var shared = window.FSQRCustomSelect;

  function enhanceSelect(nativeSelect) {
    if (!shared) return null;
    return shared.enhance(nativeSelect, {
      enhancedFlag: 'taskSelectEnhanced',
      wrapperFlag: 'taskSelect',
      compactClass: 'task-select-pill--compact',
      idPrefix: 'taskSelect_',
      syncHandle: '_taskSelectSync',
      classes: {
        wrapper: 'task-select-wrapper',
        wrapperCompact: 'task-select-wrapper--compact',
        trigger: 'task-select-trigger',
        triggerCompact: 'task-select-trigger--compact',
        triggerLabel: 'task-select-trigger__label',
        chevron: 'task-select-trigger__chevron',
        menu: 'task-select-menu',
        option: 'task-select-option',
        nativeHidden: 'task-select-pill--hidden'
      },
      interceptSetters: true,
      observeOptions: true,
      stopPropagation: true,
      alwaysDispatchChange: true,
      // 画面下部の余白が足りない場合は上方向に開く（旧 checkPosition() の挙動）。
      // Flip the menu upward when there isn't room below (old checkPosition()).
      dropUp: true
    });
  }

  function init() {
    document.querySelectorAll('select.task-select-pill').forEach(enhanceSelect);
  }

  modules.select = {
    init: init,
    enhance: enhanceSelect,
    closeAll: shared ? shared.closeAll : function () {},
    isOpen: shared ? shared.isOpen : function () { return false; },
    sync: function (select) {
      if (select && shared) shared.sync(select, '_taskSelectSync');
    }
  };
  init();
})(window, document);
