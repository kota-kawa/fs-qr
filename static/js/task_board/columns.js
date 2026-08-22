(function (window, document) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var core = modules.core;

  function columnOf(status) {
    return document.querySelector('.task-column[data-status="' + status + '"]');
  }

  function toggleCollapse(status, force) {
    var column = columnOf(status);
    if (!column) return;
    var collapsed = typeof force === 'boolean' ? force : !column.classList.contains('is-collapsed');
    column.classList.toggle('is-collapsed', collapsed);
    var button = column.querySelector('.task-column__collapse');
    if (button) {
      button.setAttribute('aria-expanded', String(!collapsed));
    }
  }

  function closeInlineAdd(form) {
    if (!form) return;
    form.hidden = true;
    var input = form.querySelector('input');
    if (input) input.value = '';
  }

  function closeAllInlineAdds(except) {
    document.querySelectorAll('.task-inline-add').forEach(function (form) {
      if (form !== except) closeInlineAdd(form);
    });
  }

  function openInlineAdd(status) {
    var column = columnOf(status);
    if (!column) return;
    toggleCollapse(status, false);

    var form = column.querySelector('.task-inline-add');
    if (!form) return;
    closeAllInlineAdds(form);
    form.hidden = false;

    var input = form.querySelector('input');
    if (input) {
      input.focus();
      input.select();
    }
  }

  async function submitInlineAdd(form, status) {
    var input = form.querySelector('input');
    var title = input ? input.value.trim() : '';
    if (!title) {
      if (input) input.focus();
      return;
    }

    var submit = form.querySelector('.task-inline-add__submit');
    if (submit) submit.disabled = true;

    try {
      await modules.actions.createItem({ title: title, board_status: status });
      if (input) {
        input.value = '';
        // Keep the composer open so several tasks can be typed in a row.
        // 連続入力できるように入力欄は開いたままにする。
        input.focus();
      }
    } catch (err) {
      core.toast(err.message || core.t('task.add_error', '追加に失敗しました。'), 'error');
      if (err.isLimit) {
        closeInlineAdd(form);
      }
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  function setMobileView(view) {
    var board = document.getElementById('taskBoard');
    if (board) board.dataset.mobileView = view;
    document.querySelectorAll('.task-status-tab').forEach(function (tab) {
      var active = tab.dataset.mobileView === view;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-pressed', String(active));
    });
  }

  function init() {
    document.addEventListener('click', function (event) {
      var addButton = event.target.closest('[data-column-add]');
      if (addButton) {
        event.preventDefault();
        openInlineAdd(addButton.dataset.columnAdd);
        return;
      }

      var menuButton = event.target.closest('[data-column-menu]');
      if (menuButton) {
        event.preventDefault();
        modules.actions.openColumnMenu(menuButton, menuButton.dataset.columnMenu);
        return;
      }

      var cancel = event.target.closest('[data-inline-cancel]');
      if (cancel) {
        event.preventDefault();
        closeInlineAdd(cancel.closest('.task-inline-add'));
      }
    });

    document.querySelectorAll('.task-inline-add').forEach(function (form) {
      var status = form.dataset.inlineAddFor;
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        submitInlineAdd(form, status);
      });
      form.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          event.stopPropagation();
          closeInlineAdd(form);
          var tool = document.querySelector('[data-column-add="' + status + '"]');
          if (tool) tool.focus();
        }
      });
    });

    document.querySelectorAll('.task-column__collapse').forEach(function (button) {
      button.addEventListener('click', function () {
        var column = button.closest('.task-column');
        if (column) toggleCollapse(column.dataset.status);
      });
    });

    document.querySelectorAll('.task-status-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        setMobileView(tab.dataset.mobileView);
      });
    });
  }

  modules.columns = {
    init: init,
    openInlineAdd: openInlineAdd,
    closeAllInlineAdds: closeAllInlineAdds,
    toggleCollapse: toggleCollapse,
    setMobileView: setMobileView
  };
})(window, document);
