/**
 * FSQR-specific share panel wiring for the info page.
 * FSQR の共有情報画面だけに必要な処理。共通部分は shared/share-panel.js に置き、
 * ここでは「URL フラグメントに載せた復号鍵を共有 URL へ付け直す」処理だけを担う。
 *
 * The decryption key never leaves the fragment (#key= / #pw=), so the value the
 * server rendered must be re-decorated on the client side.
 * 復号鍵はフラグメントにしか存在しないため、サーバーが描画した URL へ画面側で付け直す。
 */
(function (window, document) {
  'use strict';

  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var sharePanel = appNamespace.api.getShared('sharePanel');
  if (!sharePanel) {
    throw new Error('Shared share panel is not initialized.');
  }
  var helpers = appNamespace.api.getShared('runtimeHelpers');
  var translate = helpers ? helpers.translate : function (key, fallback) { return fallback || key; };

  /** Only `#key=` / `#pw=` fragments are share material. / 共有に使うのは #key= / #pw= のみ。 */
  function shareHash() {
    if (
      !window.location.hash
      || (!window.location.hash.startsWith('#key=') && !window.location.hash.startsWith('#pw='))
    ) {
      return '';
    }
    return window.location.hash;
  }

  function shareUrlWithKey(baseUrl) {
    var keyHash = shareHash();
    if (!baseUrl || !keyHash) {
      return baseUrl || '';
    }
    return baseUrl + keyHash;
  }

  sharePanel.init({
    transformShareUrl: shareUrlWithKey,
    useLocationAsShareFallback: true
  });

  document.addEventListener('DOMContentLoaded', function () {
    // Show the full URL (with key) in the visible row and on its copy button.
    // 画面に表示する URL とコピー用の値を、鍵付きの完全な URL へ差し替える。
    var shareRoomUrl = document.getElementById('shareRoomUrl');
    if (shareRoomUrl) {
      var baseShareUrl = shareRoomUrl.getAttribute('data-visible-value') || shareRoomUrl.textContent.trim();
      var fullShareUrl = shareUrlWithKey(baseShareUrl);
      if (fullShareUrl) {
        shareRoomUrl.textContent = fullShareUrl;
        shareRoomUrl.setAttribute('data-visible-value', fullShareUrl);
        var urlRow = shareRoomUrl.closest('.room-info-value-row');
        var urlCopyButton = urlRow ? urlRow.querySelector('.copy-url-button') : null;
        if (urlCopyButton) {
          urlCopyButton.setAttribute('data-copy-value', fullShareUrl);
        }
      }
    }

    // Masked value toggles (password rows). / 伏せ字の表示切り替え。
    document.querySelectorAll('.reveal-value-button').forEach(function (button) {
      button.addEventListener('click', function () {
        var targetId = button.getAttribute('data-target');
        var target = targetId ? document.getElementById(targetId) : null;
        if (!target) {
          return;
        }

        var visibleValue = target.getAttribute('data-visible-value') || '';
        var maskedValue = target.getAttribute('data-masked-value') || '••••••';
        var isMasked = target.classList.contains('is-masked');
        target.textContent = isMasked ? visibleValue : maskedValue;
        target.classList.toggle('is-masked', !isMasked);
        button.innerHTML = isMasked
          ? (button.getAttribute('data-hide-label') || translate('common.hide', 'Hide'))
          : (button.getAttribute('data-show-label') || translate('common.show', 'Show'));
      });
    });

    // Primary "copy everything" buttons use their own feedback wording.
    // 一括コピーのボタンだけは専用の文言でフィードバックする。
    document.querySelectorAll('#copyShareLinkPrimary, #copyCredentialsPrimary').forEach(function (button) {
      button.addEventListener('click', async function () {
        var text = button.getAttribute('data-copy-value') || '';
        if (!text) {
          return;
        }
        try {
          await sharePanel.copyTextToClipboard(text);
          sharePanel.setShareFeedback(
            translate('share.copy_share_success', 'Copied. You can share it as-is.'),
            'success'
          );
        } catch (error) {
          sharePanel.setShareFeedback(
            translate('share.copy_content_manual_error', 'Copy failed. Copy the displayed content manually.'),
            'error'
          );
        }
      });
    });
  });
})(window, document);
