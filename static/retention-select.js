/* Retention-select adapter for the shared accessible select implementation. */
(function (window, document) {
  'use strict';

  function init() {
    var shared = window.FSQRCustomSelect;
    if (!shared) return;
    document.querySelectorAll('[data-retention-select]').forEach(function (wrapper) {
      var nativeSelect = wrapper.querySelector('select');
      if (!nativeSelect || wrapper.dataset.retentionEnhanced === 'true') return;
      wrapper.dataset.retentionEnhanced = 'true';
      wrapper.classList.add('is-enhanced');
      var arrow = wrapper.querySelector('.retention-select-arrow');
      shared.enhance(nativeSelect, {
        enhancedFlag: 'retentionEnhanced',
        wrapper: wrapper,
        insertTriggerBefore: arrow,
        triggerIdFor: function (selectId) { return selectId + '-trigger'; },
        idPrefix: 'retention-select-',
        syncHandle: '_retentionSelectSync',
        classes: {
          trigger: 'retention-select-trigger',
          menu: 'retention-select-menu',
          option: 'retention-select-option'
        },
        stopPropagation: true,
        removeUnselectedAria: true
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window, document);
