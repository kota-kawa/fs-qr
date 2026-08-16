(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;

  var VIEWS = ['board', 'calendar'];
  var current = 'board';

  function storageKey() {
    return 'fsqr.task.view.' + (core.config.roomId || '');
  }

  function readStoredView() {
    try {
      return window.localStorage.getItem(storageKey());
    } catch (err) {
      // Private mode などで localStorage が使えない場合は既定表示のままにする。
      return null;
    }
  }

  function storeView(view) {
    try {
      window.localStorage.setItem(storageKey(), view);
    } catch (err) {
      /* 保存できなくても表示自体には影響しない。 */
    }
  }

  function updateSwitchButtons() {
    document.querySelectorAll('[data-view-switch]').forEach(function (button) {
      var active = button.dataset.viewSwitch === current;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  /** Show one view and hide the other. / 片方の表示だけを残す。 */
  function apply(view, options) {
    current = VIEWS.indexOf(view) >= 0 ? view : 'board';
    var isCalendar = current === 'calendar';

    var board = document.getElementById('taskBoard');
    var tabs = document.getElementById('taskStatusTabs');
    var calendar = document.getElementById('taskCalendar');

    if (board) board.hidden = isCalendar;
    if (tabs) tabs.hidden = isCalendar;
    if (calendar) calendar.hidden = !isCalendar;

    updateSwitchButtons();

    if (isCalendar && modules.calendar) {
      modules.calendar.refresh();
    } else if (!isCalendar && modules.render) {
      modules.render.render(modules.store.getItems(), modules.store.getCategories());
    }

    if (!options || options.persist !== false) {
      storeView(current);
    }
  }

  function toggle() {
    apply(current === 'calendar' ? 'board' : 'calendar');
  }

  function init() {
    document.querySelectorAll('[data-view-switch]').forEach(function (button) {
      button.addEventListener('click', function () {
        apply(button.dataset.viewSwitch);
      });
    });

    apply(readStoredView() || 'board', { persist: false });
  }

  modules.views = {
    init: init,
    apply: apply,
    toggle: toggle,
    getCurrent: function () {
      return current;
    }
  };
})(window, document);
