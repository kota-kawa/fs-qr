/**
 * Shared share panel behaviour for the room / info pages.
 * FSQR・Group・Note・Task の各ルーム画面で重複していた
 * 「URL コピー」「共有ボタン」「QR コード描画」「フィードバック表示」をまとめたモジュール。
 *
 * DOM contract (templates already emit these):
 *   .copy-url-button[data-copy-value | data-copy-target]  … copies a value
 *   .share-url-button[data-share-url][data-share-title]    … navigator.share or clipboard fallback
 *   .qr-code-container[data-share-url]                     … QR code target (160x160, CorrectLevel.M)
 *   #shareFeedback                                         … status toast (auto-hides after 4 s)
 *
 * Usage: window.__FSQR_APP__.api.getShared('sharePanel').init(options)
 *   options.transformShareUrl(url)  … FSQR appends the decryption key fragment
 *   options.useLocationAsShareFallback … share-url-button falls back to location.href
 *   options.copySuccessFeedback     … also show a toast after a successful button copy (Task)
 *   options.messages                … per-service {key, fallback} overrides
 */
(function (window, document) {
  var appNamespace = window.__FSQR_APP__;
  if (!appNamespace || !appNamespace.api) {
    throw new Error('App namespace is not initialized.');
  }
  var helpers = appNamespace.api.getShared('runtimeHelpers');
  if (!helpers) {
    throw new Error('Shared runtime helpers are not initialized.');
  }
  var translate = helpers.translate;

  var FEEDBACK_HIDE_MS = 4000;
  var COPIED_STATE_MS = 2000;
  var QR_SIZE = 160;

  /** Default message catalogue (Group / Note wording). / 既定文言（Group・Note と同じ）。 */
  var DEFAULT_MESSAGES = {
    copyLabel: { key: 'common.copy', fallback: 'Copy' },
    copiedLabel: { key: 'common.copied', fallback: 'Copied' },
    copySuccess: { key: 'share.copy_success', fallback: 'コピーしました。相手にそのまま送れます。' },
    copyError: { key: 'share.copy_manual_error', fallback: 'Copy failed. Display it and copy it manually.' },
    shareCopied: { key: 'share.copied_to_clipboard', fallback: 'URLをコピーしました。貼り付けて共有できます。' },
    shareCopyError: { key: 'share.copy_manual_error', fallback: 'コピーに失敗しました。URLを表示して手動でコピーしてください。' }
  };

  var settings = {
    transformShareUrl: null,
    useLocationAsShareFallback: false,
    copySuccessFeedback: false,
    messages: DEFAULT_MESSAGES
  };
  var initialized = false;
  var shareFeedbackTimer = null;

  function message(name) {
    var entry = settings.messages[name] || DEFAULT_MESSAGES[name];
    return translate(entry.key, entry.fallback);
  }

  /**
   * Copy text via the async clipboard API, falling back to execCommand('copy').
   * Clipboard API が使えない環境では非表示 textarea + execCommand で代替する。
   */
  async function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return;
      } catch (err) {
        console.error('Clipboard API failed, falling back to execCommand', err);
      }
    }

    var textarea = document.createElement('textarea');
    textarea.value = text;

    // Ensure textarea is not visible and doesn't affect layout
    Object.assign(textarea.style, {
      position: 'fixed',
      top: '0',
      left: '-9999px',
      width: '2em',
      height: '2em',
      padding: '0',
      border: 'none',
      outline: 'none',
      boxShadow: 'none',
      background: 'transparent',
      opacity: '0',
      pointerEvents: 'none'
    });

    textarea.setAttribute('readonly', '');
    document.body.appendChild(textarea);

    try {
      textarea.select();
      // Modern browsers support focus options
      if (typeof textarea.focus === 'function') {
        textarea.focus({ preventScroll: true });
      }

      if (!document.execCommand('copy')) {
        throw new Error('execCommand copy failed');
      }
    } finally {
      document.body.removeChild(textarea);
    }
  }

  /** Show the status toast and hide it again after a few seconds. / トーストを表示し、数秒後に自動で隠す。 */
  function setShareFeedback(messageText, kind) {
    var feedback = document.getElementById('shareFeedback');
    if (!feedback) {
      return;
    }
    feedback.textContent = messageText;
    feedback.className = 'share-feedback is-visible is-' + kind;
    if (shareFeedbackTimer) {
      clearTimeout(shareFeedbackTimer);
    }
    shareFeedbackTimer = setTimeout(function () {
      feedback.classList.remove('is-visible');
      shareFeedbackTimer = null;
    }, FEEDBACK_HIDE_MS);
  }

  function resolveShareUrl(url) {
    if (typeof settings.transformShareUrl === 'function') {
      return settings.transformShareUrl(url);
    }
    return url;
  }

  /** Render QR codes for every `.qr-code-container[data-share-url]`. / 共有 URL 付きのコンテナ全てに QR を描画する。 */
  function renderQrCodes(root) {
    var scope = root || document;
    if (typeof window.QRCode !== 'function') {
      return;
    }
    scope.querySelectorAll('.qr-code-container[data-share-url]').forEach(function (container) {
      var rawUrl = container.getAttribute('data-share-url') || '';
      var shareUrl = rawUrl ? resolveShareUrl(rawUrl) : '';
      if (!shareUrl) {
        return;
      }
      container.innerHTML = '';
      new window.QRCode(container, {
        text: shareUrl,
        width: QR_SIZE,
        height: QR_SIZE,
        correctLevel: window.QRCode.CorrectLevel.M
      });
    });
  }

  function readCopyText(button) {
    var targetId = button.getAttribute('data-copy-target');
    var target = targetId ? document.getElementById(targetId) : null;
    return button.getAttribute('data-copy-value')
      || (target ? (target.getAttribute('data-visible-value') || target.textContent.trim()) : '');
  }

  /** `.copy-url-button` click: copy and flip the button label for a moment. / コピー後は一定時間ラベルを切り替える。 */
  async function handleCopyButton(button) {
    var text = readCopyText(button);
    if (!text) {
      return;
    }

    var defaultLabel = button.getAttribute('data-default-label') || message('copyLabel');
    var copiedLabel = button.getAttribute('data-copied-label') || message('copiedLabel');
    if (!button.hasAttribute('aria-label')) {
      button.setAttribute('aria-label', defaultLabel);
    }
    if (!button.hasAttribute('title')) {
      button.setAttribute('title', defaultLabel);
    }

    try {
      await copyTextToClipboard(text);
      button.classList.add('copied');
      button.setAttribute('aria-label', copiedLabel);
      button.setAttribute('title', copiedLabel);
      if (settings.copySuccessFeedback) {
        setShareFeedback(message('copySuccess'), 'success');
      }
      setTimeout(function () {
        button.classList.remove('copied');
        button.setAttribute('aria-label', defaultLabel);
        button.setAttribute('title', defaultLabel);
      }, COPIED_STATE_MS);
    } catch (error) {
      setShareFeedback(message('copyError'), 'error');
    }
  }

  /** `.share-url-button` click: Web Share API, or copy the URL when unavailable. / Web Share 非対応時は URL をコピーする。 */
  async function handleShareButton(button) {
    // The transform hook only applies to template-provided URLs; location.href already
    // carries the fragment, so it must not be transformed again.
    // 変換フックはテンプレート由来の URL だけに適用する。location.href は既に
    // フラグメントを含むため二重付与しない。
    var rawUrl = button.getAttribute('data-share-url') || '';
    var url = rawUrl
      ? resolveShareUrl(rawUrl)
      : (settings.useLocationAsShareFallback ? window.location.href : '');
    if (!url) {
      return;
    }
    var title = button.getAttribute('data-share-title') || document.title;
    if (navigator.share) {
      try {
        await navigator.share({ title: title, url: url });
      } catch (error) {
        if (error && error.name === 'AbortError') {
          return;
        }
        console.error('Error sharing:', error);
      }
      return;
    }
    try {
      await copyTextToClipboard(url);
      setShareFeedback(message('shareCopied'), 'success');
    } catch (error) {
      setShareFeedback(message('shareCopyError'), 'error');
    }
  }

  /**
   * Delegated click handling so both button kinds are bound the same way,
   * regardless of when they enter the DOM.
   * 委譲方式で束ねることで、DOMContentLoaded 前後の差や動的追加の有無に左右されない。
   */
  function handleDocumentClick(event) {
    var origin = event.target instanceof Element ? event.target : null;
    if (!origin) {
      return;
    }
    var copyButton = origin.closest('.copy-url-button');
    if (copyButton) {
      handleCopyButton(copyButton);
      return;
    }
    var shareButton = origin.closest('.share-url-button');
    if (shareButton) {
      handleShareButton(shareButton);
    }
  }

  function onReady(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
    } else {
      callback();
    }
  }

  /** Apply per-service options and bind once. / サービス固有の設定を反映し、一度だけ束ねる。 */
  function init(options) {
    var opts = options || {};
    if (typeof opts.transformShareUrl === 'function') {
      settings.transformShareUrl = opts.transformShareUrl;
    }
    if (opts.useLocationAsShareFallback !== undefined) {
      settings.useLocationAsShareFallback = Boolean(opts.useLocationAsShareFallback);
    }
    if (opts.copySuccessFeedback !== undefined) {
      settings.copySuccessFeedback = Boolean(opts.copySuccessFeedback);
    }
    if (opts.messages) {
      settings.messages = Object.assign({}, DEFAULT_MESSAGES, opts.messages);
    }
    if (initialized) {
      return sharePanel;
    }
    initialized = true;
    document.addEventListener('click', handleDocumentClick);
    onReady(function () {
      renderQrCodes(document);
    });
    return sharePanel;
  }

  var sharePanel = Object.freeze({
    init: init,
    copyTextToClipboard: copyTextToClipboard,
    setShareFeedback: setShareFeedback,
    translate: translate,
    renderQrCodes: renderQrCodes,
    resolveShareUrl: resolveShareUrl
  });

  appNamespace.api.setShared('sharePanel', sharePanel);
})(window, document);
