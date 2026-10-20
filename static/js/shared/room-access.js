/* Shared access-page password toggles. / ルーム入口のパスワード表示切替。 */
(function (window, document) {
  'use strict';

  function bind(root) {
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
  }

  function init() {
    document.querySelectorAll('[data-room-access]').forEach(bind);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(window, document);
