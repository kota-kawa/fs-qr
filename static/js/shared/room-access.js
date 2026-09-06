/* Shared access tabs and password toggles. / ルーム入口の共通タブ処理。 */
(function (window, document) {
  'use strict';

  function activate(root, tabName) {
    root.querySelectorAll('[data-room-access-tab]').forEach(function (button) {
      var active = button.getAttribute('data-room-access-tab') === tabName;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    root.querySelectorAll('[data-room-access-panel]').forEach(function (panel) {
      panel.hidden = panel.getAttribute('data-room-access-panel') !== tabName;
    });
  }

  function bind(root) {
    root.querySelectorAll('[data-room-access-tab]').forEach(function (button) {
      button.addEventListener('click', function () {
        activate(root, button.getAttribute('data-room-access-tab'));
      });
    });
    root.querySelectorAll('[data-password-toggle]').forEach(function (button) {
      button.addEventListener('click', function () {
        var input = document.getElementById(button.getAttribute('data-password-toggle'));
        if (!input) return;
        var visible = input.type === 'password';
        input.type = visible ? 'text' : 'password';
        button.textContent = visible
          ? (window.FSQR_I18N ? window.FSQR_I18N.t('common.hide', '非表示') : '非表示')
          : (window.FSQR_I18N ? window.FSQR_I18N.t('common.show', '表示') : '表示');
      });
    });
    activate(root, 'join');
  }

  function init() {
    document.querySelectorAll('[data-room-access]').forEach(bind);
  }

  window.switchTab = function (tabName) {
    var root = document.querySelector('[data-room-access]');
    if (root) activate(root, tabName);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(window, document);
